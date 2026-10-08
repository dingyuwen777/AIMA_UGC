"""模拟飞书服务：一个本地 HTTP 服务器，按飞书的真实响应格式应答。

════════ 为什么这样做 ════════

要证明"配好就能登录"，最有说服力的是**走真实 HTTP**：
真实 `HttpxFeishuClient` → 真实 HTTP 请求 → 本地假飞书 → 真实 JSON 解析。

而不是像单元测试那样注入一个 Python 替身对象（那样跳过了 HTTP 层与解析层）。

**本服务按 adapter 使用的响应结构模拟应答，协议仅覆盖当前回归路径**。
字段对照见 `adapter.py`：

    POST /open-apis/auth/v3/app_access_token/internal   ← 应用令牌（token_cache 用）
    POST /open-apis/authen/v1/oidc/access_token         ← 授权码换令牌
    GET  /open-apis/authen/v1/user_info                 ← 取当前用户
    GET  /open-apis/contact/v3/group/member_belong      ← 查用户所属组
    GET  /open-apis/contact/v3/users/{open_id}          ← 查用户详情（部门 ID）
    GET  /open-apis/contact/v3/departments/{id}         ← 查部门详情
"""

# 令牌种类、授权码字段和对象路径的严格请求 Contract 继续由 Adapter 单元测试验证。

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class MockFeishuState:
    """假飞书的状态：按企业（app_id）分别配置。"""

    def __init__(self) -> None:
        # app_id -> 该企业的配置
        """初始化企业登记与测试请求记录。"""

        self.enterprises: dict[str, dict[str, Any]] = {}
        # 记录收到的请求（用于断言"用的是哪家的凭证"）
        self.requests: list[dict[str, Any]] = []

    def add_enterprise(
        self,
        *,
        app_id: str,
        app_secret: str,
        admin_group_id: str,
        user_group_id: str,
        user_open_id: str,
        user_name: str,
        department_id: str,
        department_name: str,
        member_of: tuple[str, ...],
    ) -> None:
        """注册一家企业（连同它的用户与部门）。"""

        self.enterprises[app_id] = {
            "app_id": app_id,
            "app_secret": app_secret,
            "admin_group_id": admin_group_id,
            "user_group_id": user_group_id,
            "user_open_id": user_open_id,
            "user_name": user_name,
            "department_id": department_id,
            "department_name": department_name,
            "member_of": member_of,
        }


STATE = MockFeishuState()


def _ok(data: dict[str, Any]) -> bytes:
    """编码模拟成功响应。"""

    return json.dumps({"code": 0, "msg": "success", "data": data}).encode("utf-8")


def _err(code: int, msg: str) -> bytes:
    """编码模拟错误响应，不记录凭据。"""

    return json.dumps({"code": code, "msg": msg}).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    """按飞书的真实接口形状应答。"""

    protocol_version = "HTTP/1.1"

    def log_message(self, *_: object) -> None:  # noqa: D102
        """静音默认日志（测试输出干净）。"""

    # ── 工具 ──────────────────────────────────────────────────────────
    def _read_json(self) -> dict[str, Any]:
        """只接受 JSON 对象请求，解析失败返回空对象。"""

        length = int(self.headers.get("content-length") or 0)
        if not length:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except ValueError, UnicodeDecodeError:
            return {}

    def _send(self, body: bytes, status: int = 200) -> None:
        """发送完整 JSON 响应并标明长度。"""

        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bearer(self) -> str:
        """提取测试请求中的 Bearer 值。"""

        auth = self.headers.get("authorization") or ""
        return auth[7:] if auth.lower().startswith("bearer ") else ""

    def _enterprise_of_tenant_token(self, token: str) -> dict[str, Any] | None:
        """由 tenant_access_token 反查企业（假令牌格式 `t-<app_id>`）。"""

        if not token.startswith("t-"):
            return None
        return STATE.enterprises.get(token[2:])

    # ── 路由 ──────────────────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        """处理本测试实际使用的应用令牌与授权码模拟接口。"""

        path = urlparse(self.path).path
        body = self._read_json()
        STATE.requests.append(
            {"method": "POST", "path": path, "body": body, "bearer": self._bearer()}
        )

        if path == "/open-apis/auth/v3/app_access_token/internal":
            app_id = body.get("app_id")
            ent = STATE.enterprises.get(app_id) if isinstance(app_id, str) else None
            if ent is None or body.get("app_secret") != ent["app_secret"]:
                self._send(_err(10003, "app_secret invalid"))
                return
            # ⚠️ 真实形状：tenant_access_token 与 expire 在**顶层**（不在 data 里）
            self._send(
                json.dumps(
                    {
                        "code": 0,
                        "msg": "ok",
                        "tenant_access_token": f"t-{app_id}",
                        "expire": 7200,
                    }
                ).encode("utf-8")
            )
            return

        if path == "/open-apis/authen/v1/oidc/access_token":
            ent = self._enterprise_of_tenant_token(self._bearer())
            if ent is None:
                self._send(_err(99991663, "invalid tenant token"))
                return
            if body.get("grant_type") != "authorization_code":
                self._send(_err(20001, "invalid grant_type"))
                return
            # ⚠️ 真实形状：令牌字段在 data 里
            # ⚠️ 用户令牌里**编码企业标识**（`u-<app_id>`）——
            #    因为 `/authen/v1/user_info` 只带用户令牌，服务端无从反查企业，
            #    真实飞书是"令牌本身就绑定了租户"，这里用同样思路模拟。
            self._send(
                _ok(
                    {
                        "access_token": f"u-{ent['app_id']}",
                        "refresh_token": f"r-{ent['app_id']}",
                        "expires_in": 7200,
                        "token_type": "Bearer",
                        "scope": "contact:user.base:readonly",
                    }
                )
            )
            return

        self._send(_err(404, f"no such POST path {path}"), status=404)

    def do_GET(self) -> None:  # noqa: N802
        """处理本测试实际使用的用户、群组与部门模拟接口。"""

        parsed = urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        STATE.requests.append({"method": "GET", "path": path, "query": query})

        ent = self._enterprise_of_tenant_token(self._bearer())
        # `/authen/v1/user_info` 用的是**用户令牌**（`u-<app_id>`），不是 tenant token
        is_user_info = path == "/open-apis/authen/v1/user_info"
        if is_user_info:
            token = self._bearer()
            if token.startswith("u-"):
                ent = STATE.enterprises.get(token[2:])
        if ent is None:
            self._send(_err(99991663, "invalid token"))
            return

        if is_user_info:
            self._send(
                _ok(
                    {
                        "open_id": ent["user_open_id"],
                        "union_id": f"on-{ent['user_open_id']}",
                        "name": ent["user_name"],
                        "avatar_url": "https://mock.example/avatar.png",
                    }
                )
            )
            return

        if path == "/open-apis/contact/v3/group/member_belong":
            if query.get("member_id") != ent["user_open_id"]:
                self._send(_ok({"group_list": [], "has_more": False}))
                return
            self._send(_ok({"group_list": list(ent["member_of"]), "has_more": False}))
            return

        if path.startswith("/open-apis/contact/v3/users/"):
            self._send(
                _ok(
                    {
                        "user": {
                            "open_id": ent["user_open_id"],
                            "name": None,  # ⚠️ 应用身份拿不到姓名（与真实一致）
                            "department_ids": [ent["department_id"]],
                        }
                    }
                )
            )
            return

        if path.startswith("/open-apis/contact/v3/departments/"):
            self._send(
                _ok(
                    {
                        "department": {
                            "department_id": ent["department_id"],
                            "name": ent["department_name"],
                            "parent_department_id": None,
                        }
                    }
                )
            )
            return

        self._send(_err(404, f"no such GET path {path}"), status=404)


class MockFeishuServer:
    """便于 `with` 使用的假飞书服务。"""

    def __init__(self) -> None:
        """创建仅回环可访问、动态端口的测试服务器。"""

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """服务根地址（注入给 HttpxFeishuClient）。"""

        return f"http://127.0.0.1:{self._srv.server_port}"

    def __enter__(self) -> MockFeishuServer:
        """启动服务线程并交给调用者使用。"""

        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        """关闭监听与服务线程，等待资源释放。"""

        self._srv.shutdown()
        self._srv.server_close()
        self._thread.join()
