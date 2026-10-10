"""只在显式隔离全栈环境启动真实 PostgreSQL Session 的双角色 API。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import uvicorn
from aima_ugc.bootstrap.feishu_auth_http import (
    FeishuAuthRoutes,
    FeishuAuthSettings,
    FeishuLoginRequiredResolver,
    install_feishu_auth_routes,
)
from aima_ugc.bootstrap.route_authorization import install_route_authorization
from aima_ugc.bootstrap.runtime import create_platform_runtime
from aima_ugc.entrypoints.api_main import create_app
from aima_ugc.modules.identity.feishu import SESSION_COOKIE_NAME, PrincipalStore, SessionStore
from aima_ugc.platform.config import load_settings

_ORIGIN = "http://127.0.0.1:4174"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class _NoRemoteFeishu:
    """本 Harness 只测试已签发的 AIMA Session，任何远端 SSO 调用都失败。"""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"角色全栈验收禁止远端飞书调用: {name}")

    def close(self) -> None:
        """没有外部连接需要关闭。"""


def main() -> None:
    """签发三个真实数据库会话，启动最终应用，退出时撤销本次会话。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8092)
    arguments = parser.parse_args()
    if os.environ.get("AIMA_FULLSTACK_SEED") != "1":
        raise RuntimeError("仅隔离测试库可设置 AIMA_FULLSTACK_SEED=1 启动角色验收服务")
    settings = load_settings()
    if settings.db_host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("角色验收服务仅允许本机隔离 PostgreSQL")
    token_file = arguments.token_file.absolute()
    if token_file.exists():
        raise RuntimeError("令牌输出文件已存在，拒绝覆盖未知凭据")
    runtime = create_platform_runtime("fullstack-role-sessions", settings=settings)
    tokens: list[str] = []
    token_file_created = False
    output: dict[str, Any] = {"cookie_name": SESSION_COOKIE_NAME, "origin": _ORIGIN}
    auth_settings = FeishuAuthSettings(
        app_id="cli_fullstack_role_sessions",
        admin_group_id="grp_fullstack_admin",
        user_group_id="grp_fullstack_user",
        redirect_uri=f"{_ORIGIN}/api/v1/auth/feishu/callback",
        cookie_secure=False,
    )
    try:
        with runtime.database.new_session() as session, session.begin():
            for key, name, role in (
                ("admin", "全栈管理员", "administrator"),
                ("user_a", "全栈用户甲", "user"),
                ("user_b", "全栈用户乙", "user"),
            ):
                resolved = PrincipalStore(session).resolve_or_create(
                    connector_id=auth_settings.connector_id,
                    provider="feishu",
                    provider_subject=f"fullstack-role-session:{key}",
                    display_name=name,
                )
                token = SessionStore(session).issue(
                    principal_id=resolved.principal_id,
                    display_name=resolved.display_name,
                    role=role,
                    feishu_group_ids=(
                        auth_settings.admin_group_id
                        if role == "administrator"
                        else auth_settings.user_group_id,
                    ),
                )
                tokens.append(token)
                output[key] = {
                    "principal_id": resolved.principal_id,
                    "display_name": resolved.display_name,
                    "role": role,
                    "token": token,
                }
        routes = FeishuAuthRoutes(
            auth_settings=auth_settings,
            session_factory=runtime.database.new_session,
            client=_NoRemoteFeishu(),  # type: ignore[arg-type]
        )
        resolver = FeishuLoginRequiredResolver(routes)
        application = create_app(identity_resolver=resolver)
        install_feishu_auth_routes(application, auth_routes=routes)
        install_route_authorization(application, identity_resolver=resolver)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        token_file_created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            json.dump(output, output_file, ensure_ascii=False)
        # 令牌只交给本次浏览器 Harness 文件；不写日志或命令行。
        original_send = httpx.Client.send
        original_async_send = httpx.AsyncClient.send

        def local_send(
            client: httpx.Client,
            request: httpx.Request,
            *args: Any,
            **kwargs: Any,
        ) -> httpx.Response:
            """API 仍使用生产 Adapter，但隔离验收禁止外部 HTTP 请求。"""
            if request.url.host not in _LOCAL_HOSTS:
                raise RuntimeError("角色全栈验收禁止远端 Provider HTTP 调用")
            return original_send(client, request, *args, **kwargs)

        async def local_async_send(
            client: httpx.AsyncClient,
            request: httpx.Request,
            *args: Any,
            **kwargs: Any,
        ) -> httpx.Response:
            """异步 Adapter 也遵守相同出网边界。"""
            if request.url.host not in _LOCAL_HOSTS:
                raise RuntimeError("角色全栈验收禁止远端 Provider HTTP 调用")
            return await original_async_send(client, request, *args, **kwargs)

        with (
            patch.object(httpx.Client, "send", local_send),
            patch.object(httpx.AsyncClient, "send", local_async_send),
        ):
            uvicorn.run(application, host="127.0.0.1", port=arguments.port, access_log=False)
    finally:
        try:
            if tokens:
                with runtime.database.new_session() as session, session.begin():
                    for token in tokens:
                        SessionStore(session).revoke(token)
        finally:
            try:
                if token_file_created:
                    token_file.unlink(missing_ok=True)
            finally:
                runtime.close()


if __name__ == "__main__":
    main()
