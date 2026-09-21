"""登录入口限流（S8）的单元测试：窗口语义、双轨阈值、IP 提取。

════════ 这些测试证明什么 ════════

- **滑动窗口**：只有"窗口内"的记录参与计数，窗口外的不算。
- **双轨**：全局阈值与 IP 阈值各自独立生效，任一超限都拒绝。
- **IP 取不到时仍受全局保护**（不能因为取不到 IP 就放行）。
- **`client_ip_of` 的代理语义**：有 `X-Forwarded-For` 时取最左一跳。
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from aima_ugc.modules.identity.feishu.ratelimit import (
    DEFAULT_GLOBAL_LIMIT,
    DEFAULT_IP_LIMIT,
    LoginRateLimited,
    LoginRateLimiter,
    client_ip_of,
)
from aima_ugc.modules.identity.tables import identity_login_states_table
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.time import beijing_now
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ─────────────────────────── D1 滑动窗口语义 ───────────────────────────
def test_record_outside_window_does_not_count() -> None:
    """窗口外的记录不参与计数 —— 这是"滑动"的核心，也是与固定窗口的分界。"""

    limiter = LoginRateLimiter(global_limit=2, ip_limit=10)
    session = _FakeSession(rows=[_row(ip="1.1.1.1", minutes_ago=5)], expected_ip="1.1.1.1")

    # 窗口内 0 条（窗口外那条不算）→ 放行
    limiter.check(session, client_ip="1.1.1.1")


def test_record_inside_window_counts() -> None:
    """窗口内的记录参与计数。"""

    limiter = LoginRateLimiter(global_limit=2, ip_limit=10)
    session = _FakeSession(rows=[_row(ip="1.1.1.1", minutes_ago=0)], expected_ip="1.1.1.1")

    # 窗口内 1 条 < 阈值 2 → 放行
    limiter.check(session, client_ip="1.1.1.1")


# ─────────────────────────── D2 双轨阈值 ───────────────────────────
def test_global_limit_rejects() -> None:
    """全局维度达到阈值即拒绝（即使单 IP 没超）。"""

    limiter = LoginRateLimiter(global_limit=2, ip_limit=100)
    session = _FakeSession(
        rows=[_row(ip="1.1.1.1", minutes_ago=0), _row(ip="2.2.2.2", minutes_ago=0)],
        expected_ip="3.3.3.3",
    )

    with pytest.raises(LoginRateLimited) as exc:
        limiter.check(session, client_ip="3.3.3.3")
    assert exc.value.scope == "global"
    assert exc.value.limit == 2


def test_ip_limit_rejects() -> None:
    """IP 维度达到阈值即拒绝（即使全局没超）。"""

    limiter = LoginRateLimiter(global_limit=100, ip_limit=2)
    session = _FakeSession(
        rows=[_row(ip="1.1.1.1", minutes_ago=0), _row(ip="1.1.1.1", minutes_ago=0)],
        expected_ip="1.1.1.1",
    )

    with pytest.raises(LoginRateLimited) as exc:
        limiter.check(session, client_ip="1.1.1.1")
    assert exc.value.scope == "ip"
    assert exc.value.limit == 2


def test_other_ip_does_not_consume_my_quota() -> None:
    """别人的 IP 刷量不应消耗我的 IP 配额（只受全局阈值约束）。"""

    limiter = LoginRateLimiter(global_limit=100, ip_limit=2)
    session = _FakeSession(
        rows=[_row(ip="9.9.9.9", minutes_ago=0), _row(ip="9.9.9.9", minutes_ago=0)],
        expected_ip="1.1.1.1",
    )

    # 我的 IP 为 0 条 → 放行
    limiter.check(session, client_ip="1.1.1.1")


# ─────────────────────────── D3 IP 缺失 ───────────────────────────
def test_missing_ip_still_enforces_global_limit() -> None:
    """取不到 IP 时不放行全局检查 —— 不能因为"不知道来源"就绕过限流。"""

    limiter = LoginRateLimiter(global_limit=2, ip_limit=1)
    session = _FakeSession(
        rows=[_row(ip=None, minutes_ago=0), _row(ip=None, minutes_ago=0)],
        expected_ip=None,
    )

    with pytest.raises(LoginRateLimited) as exc:
        limiter.check(session, client_ip=None)
    assert exc.value.scope == "global"


def test_missing_ip_skips_only_ip_check() -> None:
    """取不到 IP 时跳过 IP 维度检查（全局未超则放行）。"""

    limiter = LoginRateLimiter(global_limit=10, ip_limit=1)
    session = _FakeSession(rows=[_row(ip=None, minutes_ago=0)], expected_ip=None)

    limiter.check(session, client_ip=None)


# ─────────────────────────── D4 阈值校验 ───────────────────────────
@pytest.mark.parametrize(
    ("global_limit", "ip_limit", "window"),
    [
        (0, 10, timedelta(minutes=1)),
        (10, 0, timedelta(minutes=1)),
        (10, 10, timedelta(0)),
    ],
)
def test_invalid_thresholds_rejected(
    global_limit: int, ip_limit: int, window: timedelta
) -> None:
    """非法阈值在装配时就报错，不把"0 次/分钟"这类配置带进运行期。"""

    with pytest.raises(ValueError):
        LoginRateLimiter(global_limit=global_limit, ip_limit=ip_limit, window=window)


def test_defaults_match_documented_values() -> None:
    """默认阈值与方案一致：全局 240/分钟、IP 20/分钟。"""

    limiter = LoginRateLimiter()
    assert limiter.global_limit == DEFAULT_GLOBAL_LIMIT == 240
    # IP 阈值 200：见 ratelimit.py 里的说明 —— Docker 环境下所有人共用一个代理 IP 桶，
    # 20/分钟会误伤正常用户；生产环境有真实 X-Forwarded-For 时可再收紧。
    assert limiter.ip_limit == DEFAULT_IP_LIMIT == 200
    assert limiter.window == timedelta(minutes=1)


# ─────────────────────────── D5 客户端 IP 提取 ───────────────────────────
def test_client_ip_prefers_forwarded_header() -> None:
    """有反向代理头时取最左一跳（代理直连地址会误伤同代理后的所有人）。"""

    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1, 10.0.0.2"},
        client=SimpleNamespace(host="10.0.0.1"),
    )
    assert client_ip_of(request) == "203.0.113.7"


def test_client_ip_falls_back_to_direct_host() -> None:
    """没有代理头时用直连地址。"""

    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="198.51.100.9"))
    assert client_ip_of(request) == "198.51.100.9"


def test_client_ip_none_when_unavailable() -> None:
    """两者都取不到时返回 None（调用方据此只做全局检查）。"""

    request = SimpleNamespace(headers={}, client=None)
    assert client_ip_of(request) is None


def test_client_ip_truncated_to_column_width() -> None:
    """超长头被截断到 64 字符，避免把任意长的字符串写进列。"""

    request = SimpleNamespace(
        headers={"x-forwarded-for": "x" * 200}, client=None
    )
    value = client_ip_of(request)
    assert value is not None and len(value) == 64


# ═══════════════════════════ 测试替身 ═══════════════════════════
# 限流只依赖"执行一条 COUNT 查询并拿到一个数"。这里用最小替身返回预设计数，
# 让窗口语义与阈值逻辑可以脱离真实数据库被验证 —— 真实 SQL 由集成测试覆盖。
class _FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar(self) -> int:
        return self._value


class _FakeSession:
    """按"是否带 IP 条件"分别返回计数的替身。

    真实实现里两次查询的条件不同（全局 vs 带 IP）：
    第 1 次查全局，第 2 次（仅当有 IP 时）查该 IP。
    替身按**调用次序**区分，并记录第 2 次期望的 IP —— 不解析 SQL 文本，
    因为 IP 是绑定参数，不会出现在编译后的语句里。
    """

    def __init__(self, *, rows: list[dict[str, object]], expected_ip: str | None = None) -> None:
        self._rows = rows
        self._expected_ip = expected_ip
        self._call = 0

    def scalar(self, statement: object) -> int:  # noqa: ARG002 - 只看调用次序
        self._call += 1
        if self._call == 1:
            return sum(1 for r in self._rows if _in_window(r))
        # 第 2 次：只数与被检查 IP 相同的行。
        return sum(
            1
            for r in self._rows
            if _in_window(r) and r["ip"] == self._expected_ip
        )


def _row(*, ip: str | None, minutes_ago: int) -> dict[str, object]:
    """构造一条"发生在 N 分钟前"的登录发起记录。"""

    return {"ip": ip, "minutes_ago": minutes_ago}


def _in_window(row: dict[str, object]) -> bool:
    """窗口判定：分钟数 < 1 即落在过去 60 秒内。"""

    minutes = int(row["minutes_ago"])  # type: ignore[arg-type]
    return minutes < 1


# ═══════════════════ 真实 SQL 的集成校验（需要数据库）═══════════════════
@pytest.fixture
def pg_session() -> Session:
    """用环境里的 PostgreSQL 建一个空库并返回 Session；无库时跳过。"""

    import os

    host = os.environ.get("AIMA_DB_HOST")
    port = os.environ.get("AIMA_DB_PORT")
    if not host or not port:
        pytest.skip("未提供 AIMA_DB_HOST / AIMA_DB_PORT，跳过真实 SQL 校验")

    url = (
        f"postgresql+psycopg://{os.environ.get('AIMA_DB_USER', 'aima_ugc')}:"
        f"{_pg_password()}@{host}:{port}/{os.environ.get('AIMA_DB_NAME', 'aima_ugc')}"
    )
    engine = create_engine(url)
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def _pg_password() -> str:
    """从 Secret 文件读测试库密码。"""

    import os
    from pathlib import Path

    secret_dir = os.environ.get("AIMA_SECRET_DIR")
    if secret_dir:
        path = Path(secret_dir) / "postgres_password"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return "ci-postgres"


def test_real_sql_counts_only_window_rows(pg_session: Session) -> None:
    """真实 SQL：窗口外的行不计数，窗口内的计数 —— 验证滑动窗口真的生效。"""

    now = beijing_now()
    table = identity_login_states_table
    pg_session.execute(
        insert(table).values(
            [
                {
                    "state_hash": "in-window",
                    "return_to": "/",
                    "client_ip": "203.0.113.1",
                    "expires_at": now + timedelta(minutes=10),
                    "created_at": now,
                },
                {
                    "state_hash": "out-of-window",
                    "return_to": "/",
                    "client_ip": "203.0.113.1",
                    "expires_at": now + timedelta(minutes=10),
                    "consumed_at": None,
                    # 5 分钟前：落在窗口之外
                    "created_at": now - timedelta(minutes=5),
                },
            ]
        )
    )
    pg_session.commit()

    # 阈值 2 → 窗口内只有 1 条，应放行（若把窗口外那条也算进来就会误拒）
    LoginRateLimiter(global_limit=2, ip_limit=2).check(
        pg_session, client_ip="203.0.113.1"
    )
