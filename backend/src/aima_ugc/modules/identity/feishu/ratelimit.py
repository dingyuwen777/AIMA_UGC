"""登录入口限流：**滑动窗口**计数，计数存在数据库里。

════════ 为什么需要它 ════════

`/api/v1/auth/feishu/login` 是**未认证**接口 —— 不需要任何身份就能调用，
每次调用都会"写一条 state + 302 跳飞书"。它是最容易被刷的入口：
刷它既消耗数据库写入，又会把飞书侧的应用频控额度吃掉。

方案 §6.0 S8 与 §七 C2 要求：**双轨（IP + 全局）限流，且计数必须跨进程共享**。

════════ 为什么是"滑动窗口"而不是"固定窗口" ════════

固定窗口把时间切成格子（如 00:00–00:59、01:00–01:59）各自计数，会有边界突刺：

    00:59.5  打满 20 次  → 该窗口 20 次，未超
    01:00.1  又打 20 次  → 新窗口从 0 开始，也未超
    → 实际 0.6 秒内打了 40 次，限流被绕过

滑动窗口直接看"**过去 60 秒内**有多少次"，没有边界可钻。

════════ 为什么计数放数据库 ════════

方案 §七 C2 明确：内存计数在 N 个 API 进程下阈值会被放大 N 倍（限流形同虚设）。
本模块复用 `identity_login_states` 表 —— **每次发起登录本来就会写一行**，
所以"过去 60 秒的行数"天然就是"过去 60 秒的登录发起次数"：

    全局维度：COUNT(*) WHERE created_at > now() - 60s
    IP  维度：COUNT(*) WHERE created_at > now() - 60s AND client_ip = ?

**不需要**额外的计数器表，也不需要近似算法 —— 这就是精确的滑动窗口日志实现。

════════ 限流失败时的行为 ════════

超限 → 抛 `LoginRateLimited`，HTTP 层转成 **429**。
**故意不区分**"IP 超限"与"全局超限"的对外文案 —— 不给探测者额外信息。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aima_ugc.modules.identity.tables import identity_login_states_table
from aima_ugc.platform.time import beijing_now

# 滑动窗口长度：按分钟限流。
WINDOW = timedelta(minutes=1)

# 双轨阈值（方案 §6.0 S8：阈值可配置；此处给出默认值）。
#
# 全局 240/分钟来自方案 §5D.6 的容量口径。
DEFAULT_GLOBAL_LIMIT = 240
#
# IP 阈值取 200/分钟（原方案阶段 1 的 20/分钟是**直连**场景下的经验值）。
# 提高的原因与依据（2026-09-20 实测）：
#   · 本机跑在 Docker Desktop 上，容器端口经 Docker 端口代理转发，
#     nginx 的 `$remote_addr` 拿到的是**代理地址**（实测 `10.1.1.1`），
#     因此**同一台机器上的所有浏览器共享同一个 IP 桶**。
#     若仍用 20/分钟，5 个同事各自点几次就可能把桶打满，**误伤正常用户**。
#   · 生产环境是真实 nginx / 云 LB，`X-Forwarded-For` 会带真实客户端 IP，
#     不会出现"所有人共用一个桶"的情况；届时可按需调回更严的值。
#   · 200/分钟 ≈ 3.3 次/秒，实测单次请求 14ms（限流查询 12ms），
#     系统吞吐余量约 18 倍，**不会因为阈值放宽而压垮服务**。
# 结论：放宽只会减弱"单桶防刷"的强度，不会让限流失效 ——
# 超过 200 次/分钟仍会被拒（429），全局 240/分钟这一层也仍然独立生效。
DEFAULT_IP_LIMIT = 200


class LoginRateLimited(RuntimeError):
    """发起登录过于频繁（IP 维度或全局维度任一超限）。"""

    def __init__(self, *, scope: str, limit: int, observed: int) -> None:
        """记录维度、阈值与实际计数；**只用于日志**，对外不暴露。"""

        super().__init__(f"登录发起过于频繁（{scope}）")
        self.scope = scope
        self.limit = limit
        self.observed = observed


@dataclass(frozen=True, slots=True)
class LoginRateLimiter:
    """按"过去 60 秒内已发起多少次登录"判断是否放行。

    计数直接读 `identity_login_states` —— 调用方必须把本判断与"写 state"
    放在**同一个事务**里，否则并发下会出现"读到的计数偏小"的竞态。
    """

    global_limit: int = DEFAULT_GLOBAL_LIMIT
    ip_limit: int = DEFAULT_IP_LIMIT
    window: timedelta = WINDOW

    def __post_init__(self) -> None:
        """装配时校验阈值，避免把"0 次/分钟"这类配置带进运行期。"""

        if self.global_limit < 1:
            raise ValueError("全局限流阈值必须大于 0")
        if self.ip_limit < 1:
            raise ValueError("IP 限流阈值必须大于 0")
        if self.window <= timedelta(0):
            raise ValueError("限流窗口必须大于 0")

    def check(self, session: Session, *, client_ip: str | None) -> None:
        """超限时抛 `LoginRateLimited`；未超限则正常返回。

        `client_ip` 为 `None` 时**只做全局检查** —— 取不到 IP 不是拒绝登录的理由
        （反向代理配置差异、测试环境等都可能取不到），此时仍受全局阈值保护。
        """

        since = beijing_now() - self.window

        # ① 全局维度：过去一个窗口内所有登录发起
        global_count = int(
            session.scalar(
                select(func.count())
                .select_from(identity_login_states_table)
                .where(identity_login_states_table.c.created_at > since)
            )
            or 0
        )
        if global_count >= self.global_limit:
            raise LoginRateLimited(
                scope="global", limit=self.global_limit, observed=global_count
            )

        # ② IP 维度：过去一个窗口内同一来源
        if client_ip:
            ip_count = int(
                session.scalar(
                    select(func.count())
                    .select_from(identity_login_states_table)
                    .where(
                        identity_login_states_table.c.created_at > since,
                        identity_login_states_table.c.client_ip == client_ip,
                    )
                )
                or 0
            )
            if ip_count >= self.ip_limit:
                raise LoginRateLimited(
                    scope="ip", limit=self.ip_limit, observed=ip_count
                )


def client_ip_of(request: object) -> str | None:
    """从请求里取客户端 IP；取不到返回 `None`。

    ⚠️ 取值顺序刻意是"**先看反向代理头、再看直连地址**"：

    - 部署在 nginx / 网关后面时，`request.client.host` 是**代理的地址**，
      同一代理后面的所有用户会共享一个 IP —— 拿它限流会误伤整栋楼的人。
      此时应信任代理透传的 `X-Forwarded-For` **最左第一跳**。
    - 没有代理时 `X-Forwarded-For` 不存在，回退到直连地址。

    ⚠️ `X-Forwarded-For` **可被伪造**。这里的取舍是：
    限流的目标是"挡住无脑刷量"，不是"精确识别攻击者"。
    伪造该头只能**换一个被限流的桶**，并不能绕过全局阈值 ——
    所以不额外引入"可信代理白名单"这一层复杂度。
    """

    headers = getattr(request, "headers", None)
    if headers is not None:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            # 形如 "client, proxy1, proxy2"：取最左一跳，去掉空白。
            first = str(forwarded).split(",")[0].strip()
            if first:
                return first[:64]

    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    if host is None:
        return None
    return str(host)[:64]


__all__ = [
    "DEFAULT_GLOBAL_LIMIT",
    "DEFAULT_IP_LIMIT",
    "WINDOW",
    "LoginRateLimited",
    "LoginRateLimiter",
    "client_ip_of",
]
