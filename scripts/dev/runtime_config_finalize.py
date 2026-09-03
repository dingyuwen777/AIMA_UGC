#!/usr/bin/env python3
"""Temporary PR finalizer for CHG-20260903-runtime-config-control-plane.

This file is removed by the temporary workflow before the final implementation
commit is pushed. It exists only because the connected development environment
cannot clone GitHub directly, while the repository runner can run generators,
formatters and targeted tests against the real checkout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd or ROOT, check=True)


def git_show_main(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"origin/main:{path}"], cwd=ROOT, text=True
    )


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def provider_contract_block() -> str:
    return '''\n\nclass ProviderConfigCreateRequest(BaseModel):
    """创建管理员可维护 Provider；API Key 仅用于本次写入，不进入响应或数据库。"""

    model_config = ConfigDict(extra="forbid")
    provider_kind: ProviderKind
    provider: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$",
    )
    display_name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: SecretStr
    timeout_seconds: int = Field(default=45, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=20)
    max_concurrency: int = Field(default=5, ge=1, le=500)
    max_rps: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool = True
    is_default: bool = False

    @field_validator("provider", "display_name", "base_url", "model", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        """清理 Provider 管理文本字段。"""

        return _trimmed(value)

    @model_validator(mode="after")
    def validate_provider(self) -> ProviderConfigCreateRequest:
        """校验 Provider Kind 与模型/default 语义。"""

        if not self.api_key.get_secret_value():
            raise ValueError("api_key 不能为空")
        if self.provider_kind == "llm" and not self.model:
            raise ValueError("LLM Provider 必须配置 model")
        if self.provider_kind == "collection" and self.model is not None:
            raise ValueError("采集 Provider 不使用 model")
        if self.provider_kind == "collection" and self.is_default:
            raise ValueError("采集 Provider 由采集计划显式引用，不使用默认标记")
        if self.is_default and not self.enabled:
            raise ValueError("默认 Provider 必须启用")
        return self


class ProviderConfigUpdateRequest(BaseModel):
    """完整替换可变 Provider 字段；省略 api_key 表示不轮换 Secret。"""

    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: SecretStr | None = None
    timeout_seconds: int = Field(default=45, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=20)
    max_concurrency: int = Field(default=5, ge=1, le=500)
    max_rps: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool = True
    is_default: bool = False

    @field_validator("display_name", "base_url", "model", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        """清理 Provider 可变文本字段。"""

        return _trimmed(value)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        """显式空 API Key 不等价于“不轮换”。"""

        if value is not None and not value.get_secret_value():
            raise ValueError("api_key 为空时请省略该字段")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> ProviderConfigUpdateRequest:
        """默认 Provider 必须处于启用状态。"""

        if self.is_default and not self.enabled:
            raise ValueError("默认 Provider 必须启用")
        return self


class ProviderConfigResponse(BaseModel):
    """Provider 管理安全投影；绝不返回 API Key 或内部 secret_ref。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    provider_kind: ProviderKind
    provider: str
    display_name: str
    base_url: str
    model: str | None = None
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    max_concurrency: int = Field(gt=0)
    max_rps: int | None = Field(default=None, gt=0)
    enabled: bool
    is_default: bool
    revision: int = Field(gt=0)
    secret_configured: bool


class ProviderConfigListResponse(BaseModel):
    """管理员 Provider 配置目录安全投影。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[ProviderConfigResponse, ...]
'''


def patch_administration_contract() -> None:
    path = "backend/src/aima_ugc/contracts/administration.py"
    text = git_show_main(path)
    text = replace_once(
        text,
        "from pydantic import ConfigDict, Field, computed_field, field_validator, model_validator",
        "from pydantic import (\n"
        "    ConfigDict,\n"
        "    Field,\n"
        "    SecretStr,\n"
        "    computed_field,\n"
        "    field_validator,\n"
        "    model_validator,\n"
        ")",
        label="administration pydantic imports",
    )
    text = replace_once(
        text,
        'AnalysisSchemeVersionStatus = Literal["draft", "published", "retired"]\n',
        'AnalysisSchemeVersionStatus = Literal["draft", "published", "retired"]\n'
        'ProviderKind = Literal["collection", "llm"]\n',
        label="ProviderKind insertion",
    )
    text = replace_once(
        text,
        "\n\nclass AuditEventListQuery(BaseModel):",
        provider_contract_block() + "\n\nclass AuditEventListQuery(BaseModel):",
        label="provider contract insertion",
    )
    text = replace_once(
        text,
        '    "PrincipalRole",\n',
        '    "PrincipalRole",\n'
        '    "ProviderConfigCreateRequest",\n'
        '    "ProviderConfigListResponse",\n'
        '    "ProviderConfigResponse",\n'
        '    "ProviderConfigUpdateRequest",\n'
        '    "ProviderKind",\n',
        label="provider contract exports",
    )
    write(path, text)


def patch_administration_protocol() -> None:
    path = "backend/src/aima_ugc/modules/administration/http.py"
    text = git_show_main(path)
    text = replace_once(
        text,
        "    KeywordPackVehicleLinksResponse,\n",
        "    KeywordPackVehicleLinksResponse,\n"
        "    ProviderConfigCreateRequest,\n"
        "    ProviderConfigListResponse,\n"
        "    ProviderConfigResponse,\n"
        "    ProviderConfigUpdateRequest,\n"
        "    ProviderKind,\n",
        label="administration protocol imports",
    )
    methods = '''\n    def list_provider_configs(
        self,
        *,
        provider_kind: ProviderKind | None = None,
    ) -> ProviderConfigListResponse:
        """管理员读取 LLM/TikHub Provider 安全投影。"""

        ...

    def create_provider_config(
        self,
        body: ProviderConfigCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """管理员创建 Provider 与不可变 Secret 引用。"""

        ...

    def update_provider_config(
        self,
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """管理员修改 Provider；可选择轮换 Secret。"""

        ...
\n'''
    text = replace_once(
        text,
        "    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:\n",
        methods
        + "    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:\n",
        label="administration protocol methods",
    )
    write(path, text)


def provider_service_methods() -> str:
    return '''    def list_provider_configs(
        self,
        *,
        provider_kind: ProviderKind | None = None,
    ) -> ProviderConfigListResponse:
        """管理员只读取 Provider 安全投影，绝不暴露 API Key/secret_ref。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configs = PostgresProviderConfigRepository(session).list_all(
                    provider_kind=provider_kind
                )
                return ProviderConfigListResponse(
                    items=tuple(_provider_response(item) for item in configs)
                )
        finally:
            session.close()

    def create_provider_config(
        self,
        body: ProviderConfigCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """创建 Provider；Secret 只写批准的持久化 Provider Secret Store。"""

        principal.require_administrator()
        config_id = uuid4()
        secret_ref = new_secret_ref(config_id, uuid4().hex)
        try:
            candidate = ProviderConfig(
                id=config_id,
                provider=body.provider,
                provider_kind=body.provider_kind,
                display_name=body.display_name,
                base_url=body.base_url,
                model=body.model,
                secret_ref=secret_ref,
                timeout_seconds=body.timeout_seconds,
                max_retries=body.max_retries,
                max_concurrency=body.max_concurrency,
                max_rps=body.max_rps,
                is_default=body.is_default,
                revision=1,
                enabled=body.enabled,
            )
            write_secret_ref(
                self._runtime.settings.external_secret_root,
                secret_ref,
                body.api_key,
            )
        except (ValueError, SecretFileError) as exc:
            raise AdministrationConflict from exc

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                created = PostgresProviderConfigRepository(session).create(candidate)
                _audit_provider(
                    session,
                    principal,
                    request_id,
                    "provider_config_created",
                    created,
                    secret_rotated=True,
                )
                return _provider_response(created)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def update_provider_config(
        self,
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """更新 Provider；省略 API Key 时保持原不可变 Secret 引用。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigRepository(session)
                current = repository.get(provider_config_id)
                if current is None:
                    raise AdministrationResourceNotFound
                if current.provider_kind == "llm" and not body.model:
                    raise AdministrationConflict("LLM Provider 必须配置 model")
                if current.provider_kind == "collection" and body.model is not None:
                    raise AdministrationConflict("采集 Provider 不使用 model")
                if current.provider_kind == "collection" and body.is_default:
                    raise AdministrationConflict("采集 Provider 不使用默认标记")

                secret_ref = current.secret_ref
                secret_rotated = body.api_key is not None
                if body.api_key is not None:
                    secret_ref = new_secret_ref(provider_config_id, uuid4().hex)
                    try:
                        write_secret_ref(
                            self._runtime.settings.external_secret_root,
                            secret_ref,
                            body.api_key,
                        )
                    except (ValueError, SecretFileError) as exc:
                        raise AdministrationConflict from exc
                try:
                    updated = repository.update_settings(
                        provider_config_id,
                        display_name=body.display_name,
                        base_url=body.base_url,
                        model=body.model,
                        secret_ref=secret_ref,
                        timeout_seconds=body.timeout_seconds,
                        max_retries=body.max_retries,
                        max_concurrency=body.max_concurrency,
                        max_rps=body.max_rps,
                        enabled=body.enabled,
                        is_default=body.is_default,
                    )
                except (KeyError, ValueError) as exc:
                    raise AdministrationConflict from exc
                _audit_provider(
                    session,
                    principal,
                    request_id,
                    "provider_config_updated",
                    updated,
                    secret_rotated=secret_rotated,
                )
                return _provider_response(updated)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

'''


def patch_administration_service() -> None:
    path = "backend/src/aima_ugc/bootstrap/administration_http.py"
    text = git_show_main(path)
    text = replace_once(
        text,
        "from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository\n",
        "from aima_ugc.adapters.persistence.postgres.system import (\n"
        "    PostgresAuditRepository,\n"
        "    PostgresProviderConfigRepository,\n"
        ")\n",
        label="administration repository imports",
    )
    text = replace_once(
        text,
        "    KeywordPackVehicleLinksResponse,\n",
        "    KeywordPackVehicleLinksResponse,\n"
        "    ProviderConfigCreateRequest,\n"
        "    ProviderConfigListResponse,\n"
        "    ProviderConfigResponse,\n"
        "    ProviderConfigUpdateRequest,\n"
        "    ProviderKind,\n",
        label="administration contract imports",
    )
    text = replace_once(
        text,
        "from aima_ugc.modules.system.models import AuditEvent\n",
        "from aima_ugc.modules.system.models import AuditEvent, ProviderConfig\n",
        label="administration system model imports",
    )
    text = replace_once(
        text,
        "from aima_ugc.platform.time import beijing_now\n\nfrom .runtime import PlatformRuntime\n",
        "from aima_ugc.platform.security import SecretFileError, write_secret_ref\n"
        "from aima_ugc.platform.time import beijing_now\n\n"
        "from .runtime import PlatformRuntime\n"
        "from .runtime_config import new_secret_ref\n",
        label="administration secret imports",
    )
    text = replace_once(
        text,
        "    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:\n",
        provider_service_methods()
        + "    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:\n",
        label="administration provider methods",
    )
    helper = '''\n\ndef _provider_response(config: ProviderConfig) -> ProviderConfigResponse:
    """投影不包含 API Key 或内部 Secret 路径。"""

    return ProviderConfigResponse(
        id=config.id,
        provider_kind=config.provider_kind,
        provider=config.provider,
        display_name=config.display_name,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        max_concurrency=config.max_concurrency,
        max_rps=config.max_rps,
        enabled=config.enabled,
        is_default=config.is_default,
        revision=config.revision,
        secret_configured=bool(config.secret_ref),
    )
'''
    text = replace_once(
        text,
        "\n\ndef _scheme_response(\n",
        helper + "\n\ndef _scheme_response(\n",
        label="administration provider response helper",
    )
    audit_helper = '''\n\ndef _audit_provider(
    session: Any,
    principal: Principal,
    request_id: str,
    event_type: str,
    config: ProviderConfig,
    *,
    secret_rotated: bool,
) -> None:
    """审计 Provider 非敏感事实，不记录 secret_ref 或 Secret 值。"""

    _audit(
        session,
        principal=principal,
        request_id=request_id,
        event_type=event_type,
        object_type="provider_config",
        object_id=str(config.id),
        detail={
            "provider_kind": config.provider_kind,
            "provider": config.provider,
            "revision": config.revision,
            "enabled": config.enabled,
            "is_default": config.is_default,
            "secret_rotated": secret_rotated,
        },
    )
'''
    text = replace_once(
        text,
        "\n\ndef _audit_scheme(\n",
        audit_helper + "\n\ndef _audit_scheme(\n",
        label="administration provider audit helper",
    )
    write(path, text)


def patch_analysis_repository() -> None:
    path = "backend/src/aima_ugc/adapters/persistence/postgres/analysis.py"
    text = git_show_main(path)
    text = replace_once(
        text,
        "        generation_config_hash: str,\n        analysis_scheme_version_id: UUID | None = None,\n",
        "        generation_config_hash: str,\n"
        "        runtime_config_snapshot: dict[str, object] | None = None,\n"
        "        analysis_scheme_version_id: UUID | None = None,\n",
        label="analysis run signature",
    )
    text = replace_once(
        text,
        "                    generation_config_hash=generation_config_hash,\n                    created_at=beijing_now(),\n",
        "                    generation_config_hash=generation_config_hash,\n"
        "                    runtime_config_snapshot=runtime_config_snapshot or {},\n"
        "                    created_at=beijing_now(),\n",
        label="analysis run snapshot persist",
    )
    write(path, text)


def patch_api_routes() -> None:
    path = "backend/src/aima_ugc/bootstrap/api.py"
    text = read(path)
    text = replace_once(
        text,
        "    KeywordPackVehicleLinksResponse,\n",
        "    KeywordPackVehicleLinksResponse,\n"
        "    ProviderConfigCreateRequest,\n"
        "    ProviderConfigListResponse,\n"
        "    ProviderConfigResponse,\n"
        "    ProviderConfigUpdateRequest,\n"
        "    ProviderKind,\n",
        label="api provider imports",
    )
    routes = '''\n    @application.get(
        "/api/v1/provider-configs",
        operation_id="listProviderConfigs",
        response_model=ProviderConfigListResponse,
        responses={
            403: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def list_provider_configs(
        request: Request,
        provider_kind: Annotated[ProviderKind | None, Query()] = None,
    ) -> ProviderConfigListResponse:
        """管理员读取 Provider 安全投影；不返回 Secret 值或 secret_ref。"""

        current_principal(request).require_administrator()
        return current_administration_service().list_provider_configs(
            provider_kind=provider_kind
        )

    @application.post(
        "/api/v1/provider-configs",
        operation_id="createProviderConfig",
        response_model=ProviderConfigResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def create_provider_config(
        body: ProviderConfigCreateRequest,
        request: Request,
    ) -> ProviderConfigResponse:
        """管理员创建 Provider；API Key 仅进入后端 Secret Store 写入边界。"""

        return current_administration_service().create_provider_config(
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.put(
        "/api/v1/provider-configs/{provider_config_id}",
        operation_id="updateProviderConfig",
        response_model=ProviderConfigResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def update_provider_config(
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        request: Request,
    ) -> ProviderConfigResponse:
        """管理员更新 Provider；省略 API Key 时保持当前 Secret 引用。"""

        return current_administration_service().update_provider_config(
            provider_config_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )
\n'''
    text = replace_once(
        text,
        "    @application.post(\n        \"/api/v1/vehicle-models\",\n",
        routes + "    @application.post(\n        \"/api/v1/vehicle-models\",\n",
        label="api provider routes",
    )
    write(path, text)
    write("backend/src/aima_ugc/entrypoints/api_main.py", git_show_main("backend/src/aima_ugc/entrypoints/api_main.py"))
    (ROOT / "backend/src/aima_ugc/bootstrap/provider_configuration_http.py").unlink(missing_ok=True)


def patch_provider_identity() -> None:
    path = "backend/src/aima_ugc/modules/system/models.py"
    text = read(path)
    text = replace_once(
        text,
        're.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")',
        're.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")',
        label="LLM provider identity regex",
    )
    write(path, text)


def patch_collection_snapshot_restore() -> None:
    path = "backend/src/aima_ugc/bootstrap/collection_scope.py"
    text = read(path)
    old_dataclass = '''class _PlatformRuntimeConfig:
    provider_config_id: UUID
    config: dict[str, object]
    provider: str | None = None
    base_url: str | None = None
    secret_ref: str | None = None
'''
    new_dataclass = '''class _PlatformRuntimeConfig:
    provider_config_id: UUID
    config: dict[str, object]
    provider_kind: str | None = None
    provider: str | None = None
    base_url: str | None = None
    secret_ref: str | None = None
    timeout_seconds: int | None = None
    max_retries: int | None = None
    max_concurrency: int | None = None
    max_rps: int | None = None
    extra_config: dict[str, object] | None = None
    revision: int | None = None
'''
    text = replace_once(text, old_dataclass, new_dataclass, label="collection runtime dataclass")
    old_provider = '''        if (
            runtime_config.provider is not None
            and runtime_config.base_url is not None
            and runtime_config.secret_ref is not None
        ):
            if runtime_config.provider != "tikhub":
                raise ValueError("TikHub Scope Runtime 只接受 provider=tikhub")
            return ProviderConfig(
                id=runtime_config.provider_config_id,
                provider=runtime_config.provider,
                display_name=f"run-snapshot:{runtime_config.provider_config_id}",
                base_url=runtime_config.base_url,
                secret_ref=runtime_config.secret_ref,
                enabled=True,
            )
'''
    new_provider = '''        if (
            runtime_config.provider is not None
            and runtime_config.base_url is not None
            and runtime_config.secret_ref is not None
        ):
            if runtime_config.provider_kind not in {None, "collection"}:
                raise ValueError("TikHub Scope Runtime Snapshot provider_kind 必须为 collection")
            if runtime_config.provider != "tikhub":
                raise ValueError("TikHub Scope Runtime 只接受 provider=tikhub")
            return ProviderConfig(
                id=runtime_config.provider_config_id,
                provider=runtime_config.provider,
                provider_kind="collection",
                display_name=f"run-snapshot:{runtime_config.provider_config_id}",
                base_url=runtime_config.base_url,
                secret_ref=runtime_config.secret_ref,
                timeout_seconds=runtime_config.timeout_seconds or 45,
                max_retries=(
                    3 if runtime_config.max_retries is None else runtime_config.max_retries
                ),
                max_concurrency=runtime_config.max_concurrency or 5,
                max_rps=runtime_config.max_rps,
                extra_config=runtime_config.extra_config or {},
                revision=runtime_config.revision or 1,
                enabled=True,
            )
'''
    text = replace_once(text, old_provider, new_provider, label="collection provider snapshot restore")
    old_parse = '''    provider = item.get("provider")
    base_url = item.get("base_url")
    secret_ref = item.get("secret_ref")
    return _PlatformRuntimeConfig(
        provider_config_id=parsed_config_id,
        config={str(key): value for key, value in config.items()},
        provider=provider if isinstance(provider, str) else None,
        base_url=base_url if isinstance(base_url, str) else None,
        secret_ref=(secret_ref if isinstance(secret_ref, str) else None),
    )
'''
    new_parse = '''    provider_kind = item.get("provider_kind")
    provider = item.get("provider")
    base_url = item.get("base_url")
    secret_ref = item.get("secret_ref")
    extra_config = item.get("extra_config", {})
    if not isinstance(extra_config, dict):
        raise ValueError("Collection Run Snapshot extra_config 必须为对象")
    return _PlatformRuntimeConfig(
        provider_config_id=parsed_config_id,
        config={str(key): value for key, value in config.items()},
        provider_kind=provider_kind if isinstance(provider_kind, str) else None,
        provider=provider if isinstance(provider, str) else None,
        base_url=base_url if isinstance(base_url, str) else None,
        secret_ref=(secret_ref if isinstance(secret_ref, str) else None),
        timeout_seconds=_optional_snapshot_int(item, "timeout_seconds", minimum=1),
        max_retries=_optional_snapshot_int(item, "max_retries", minimum=0),
        max_concurrency=_optional_snapshot_int(item, "max_concurrency", minimum=1),
        max_rps=_optional_snapshot_int(item, "max_rps", minimum=1),
        extra_config={str(key): value for key, value in extra_config.items()},
        revision=_optional_snapshot_int(item, "revision", minimum=1),
    )
'''
    text = replace_once(text, old_parse, new_parse, label="collection snapshot parser")
    helper = '''\n\ndef _optional_snapshot_int(
    payload: dict[str, object],
    name: str,
    *,
    minimum: int,
) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Collection Run Snapshot {name} 不合法")
    return value
'''
    text = replace_once(
        text,
        "\n\ndef _decision_policy(\n",
        helper + "\n\ndef _decision_policy(\n",
        label="collection snapshot integer helper",
    )
    write(path, text)


def patch_internal_bootstrap() -> None:
    path = "backend/src/aima_ugc/bootstrap/internal_v1.py"
    text = read(path)
    text = replace_once(
        text,
        "from dataclasses import dataclass\n",
        "from dataclasses import dataclass\nfrom pathlib import Path\n",
        label="internal bootstrap Path import",
    )
    text = replace_once(
        text,
        "from aima_ugc.platform.security import read_secret_file, validate_secret_ref\n",
        "from aima_ugc.platform.security import (\n"
        "    read_secret_file,\n"
        "    read_secret_ref,\n"
        "    validate_secret_ref,\n"
        "    write_secret_ref,\n"
        ")\n",
        label="internal bootstrap secret imports",
    )
    text = replace_once(
        text,
        '_DEFAULT_TIKHUB_SECRET_REF = "tikhub_api_key"\n',
        '_DEFAULT_TIKHUB_SECRET_REF = "tikhub_api_key"\n'
        '_DEFAULT_BOOTSTRAP_SECRET_DIR = Path("/run/secrets")\n',
        label="bootstrap secret root constant",
    )
    copy_helpers = '''\n\ndef bootstrap_internal_v1_external_secrets(
    settings: PlatformSettings,
    provider: InternalV1ProviderSettings,
    *,
    bootstrap_secret_dir: Path | None = None,
) -> None:
    """把部署注入 Secret 首次复制到持久化 Provider Secret Store，之后禁止覆盖。"""

    source_root = (bootstrap_secret_dir or _DEFAULT_BOOTSTRAP_SECRET_DIR).resolve(
        strict=True
    )
    if provider.enabled:
        _copy_bootstrap_secret_once(
            settings,
            source_root=source_root,
            source_name="tikhub_api_key",
            target_ref=provider.secret_ref,
        )
    if any(
        value is not None
        for value in (
            settings.llm_base_url,
            settings.llm_provider_name,
            settings.llm_model,
        )
    ):
        _copy_bootstrap_secret_once(
            settings,
            source_root=source_root,
            source_name="llm_api_key",
            target_ref="llm_api_key",
        )


def _copy_bootstrap_secret_once(
    settings: PlatformSettings,
    *,
    source_root: Path,
    source_name: str,
    target_ref: str,
) -> None:
    """已有持久化 Secret 只校验不覆盖，避免重启把管理员轮换结果改回环境值。"""

    target = settings.external_secret_root / target_ref
    if target.exists() or target.is_symlink():
        read_secret_ref(settings.external_secret_root, target_ref)
        return
    source = read_secret_file(source_root / source_name, root=source_root)
    write_secret_ref(settings.external_secret_root, target_ref, source)
'''
    text = replace_once(
        text,
        "\n\ndef validate_internal_v1_provider_secret(\n",
        copy_helpers + "\n\ndef validate_internal_v1_provider_secret(\n",
        label="bootstrap external secret copy",
    )
    old_provision = '''    validate_internal_v1_provider_secret(settings, provider)
    repository = PostgresProviderConfigRepository(session)
    config_id = internal_v1_tikhub_provider_config_id()
    current = repository.get(config_id)

    if current is None and not provider.enabled:
        return None
    if current is not None and current.provider != "tikhub":
        raise RuntimeError("Internal V1 稳定 Provider Config UUID 已被其他 Provider 占用")

    desired = ProviderConfig(
'''
    new_provision = '''    repository = PostgresProviderConfigRepository(session)
    config_id = internal_v1_tikhub_provider_config_id()
    current = repository.get(config_id)
    if current is not None:
        if current.provider != "tikhub":
            raise RuntimeError("Internal V1 稳定 Provider Config UUID 已被其他 Provider 占用")
        # `.env` 只负责首次 bootstrap；数据库记录存在后由管理员控制面维护，启动不得回写。
        return current
    if not provider.enabled:
        return None

    validate_internal_v1_provider_secret(settings, provider)
    desired = ProviderConfig(
'''
    text = replace_once(text, old_provision, new_provision, label="DB authoritative TikHub bootstrap")
    old_tail = '''    if current is None:
        return repository.create(desired)
    if current == desired:
        return current
    return repository.update_settings(
        config_id,
        display_name=desired.display_name,
        base_url=desired.base_url,
        secret_ref=desired.secret_ref,
        enabled=desired.enabled,
    )
'''
    text = replace_once(
        text,
        old_tail,
        "    return repository.create(desired)\n",
        label="bootstrap create only",
    )
    text = replace_once(
        text,
        '    "InternalV1ProviderSettings",\n',
        '    "InternalV1ProviderSettings",\n'
        '    "bootstrap_internal_v1_external_secrets",\n',
        label="bootstrap export",
    )
    write(path, text)

    entry = "backend/src/aima_ugc/entrypoints/internal_v1_configure_main.py"
    text = read(entry)
    text = replace_once(
        text,
        "from aima_ugc.bootstrap.internal_v1 import (\n",
        "from aima_ugc.bootstrap.internal_v1 import (\n"
        "    bootstrap_internal_v1_external_secrets,\n",
        label="configure bootstrap import",
    )
    text = replace_once(
        text,
        "    provider = load_internal_v1_provider_settings()\n    llm_configured = validate_internal_v1_llm_settings(settings)\n",
        "    provider = load_internal_v1_provider_settings()\n"
        "    bootstrap_internal_v1_external_secrets(settings, provider)\n"
        "    llm_configured = validate_internal_v1_llm_settings(settings)\n",
        label="configure bootstrap copy call",
    )
    write(entry, text)


def backend_volume_block(*, provider_read_only: bool) -> str:
    readonly = "\n      read_only: true" if provider_read_only else ""
    return f'''    volumes:
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/runtime/data
        target: /app/data
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/runtime/logs
        target: /app/logs
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/shared/secrets
        target: /run/internal-secrets
        read_only: true
      - type: bind
        source: ${{AIMA_HISTORICAL_IMPORT_HOST_ROOT:-/data/aima-historical-input}}
        target: /data/aima-historical-input
        read_only: true
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/shared/provider-secrets
        target: /run/provider-secrets{readonly}
'''


def patch_compose() -> None:
    path = "compose.yaml"
    text = read(path)
    text = replace_once(
        text,
        "  - AIMA_EXTERNAL_SECRET_DIR=/run/secrets\n",
        "  - AIMA_EXTERNAL_SECRET_DIR=/run/provider-secrets\n",
        label="compose external secret root",
    )
    text = replace_once(
        text,
        "      - type: bind\n        source: ${AIMA_HOST_ROOT:-/data/AIMA_UGC}/shared/secrets\n        target: /host/shared/secrets\n",
        "      - type: bind\n"
        "        source: ${AIMA_HOST_ROOT:-/data/AIMA_UGC}/shared/secrets\n"
        "        target: /host/shared/secrets\n"
        "      - type: bind\n"
        "        source: ${AIMA_HOST_ROOT:-/data/AIMA_UGC}/shared/provider-secrets\n"
        "        target: /host/shared/provider-secrets\n",
        label="bootstrap provider secret mount",
    )
    text = replace_once(
        text,
        '  configure:\n    <<: *backend-service\n    command: ["python", "-m", "aima_ugc.entrypoints.internal_v1_configure_main"]\n',
        '  configure:\n    <<: *backend-service\n'
        '    command: ["python", "-m", "aima_ugc.entrypoints.internal_v1_configure_main"]\n'
        + backend_volume_block(provider_read_only=False),
        label="configure provider secret mount",
    )
    text = replace_once(
        text,
        '  api:\n    <<: *backend-service\n    command: ["uvicorn", "aima_ugc.entrypoints.api_main:app", "--host", "0.0.0.0", "--port", "8090"]\n    secrets:\n      - llm_api_key\n',
        '  api:\n    <<: *backend-service\n'
        '    command: ["uvicorn", "aima_ugc.entrypoints.api_main:app", "--host", "0.0.0.0", "--port", "8090"]\n'
        + backend_volume_block(provider_read_only=False),
        label="api provider secret mount",
    )
    text = replace_once(
        text,
        '  worker:\n    <<: *backend-service\n    command: ["python", "-m", "aima_ugc.entrypoints.worker_main"]\n    secrets:\n      - tikhub_api_key\n      - llm_api_key\n',
        '  worker:\n    <<: *backend-service\n'
        '    command: ["python", "-m", "aima_ugc.entrypoints.worker_main"]\n'
        + backend_volume_block(provider_read_only=True),
        label="worker provider secret mount",
    )
    write(path, text)

    host = "scripts/deploy/prepare_host.py"
    text = read(host)
    text = replace_once(
        text,
        '    DirectorySpec("shared/secrets", 0, SECRET_GID, 0o750),\n',
        '    DirectorySpec("shared/secrets", 0, SECRET_GID, 0o750),\n'
        '    DirectorySpec("shared/provider-secrets", APP_UID, APP_GID, 0o700),\n',
        label="provider secret host directory",
    )
    write(host, text)


def windows_volume_block(*, provider_read_only: bool) -> str:
    readonly = "\n        read_only: true" if provider_read_only else ""
    return f'''    volumes:
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/runtime/data
        target: /app/data
      - type: bind
        source: ${{AIMA_HOST_ROOT:-/data/AIMA_UGC}}/runtime/logs
        target: /app/logs
      - type: volume
        source: windows_internal_secrets
        target: /run/internal-secrets
        read_only: true
      - type: bind
        source: ${{AIMA_HISTORICAL_IMPORT_HOST_ROOT:-./.runtime/historical-input}}
        target: /data/aima-historical-input
        read_only: true
      - type: volume
        source: windows_provider_secrets
        target: /run/provider-secrets{readonly}
'''


def patch_windows_compose() -> None:
    path = "compose.windows.yaml"
    text = read(path)
    text = replace_once(
        text,
        "      - type: volume\n        source: windows_internal_secrets\n        target: /host/shared/secrets\n",
        "      - type: volume\n"
        "        source: windows_internal_secrets\n"
        "        target: /host/shared/secrets\n"
        "      - type: volume\n"
        "        source: windows_provider_secrets\n"
        "        target: /host/shared/provider-secrets\n",
        label="windows bootstrap provider store",
    )
    text = replace_once(
        text,
        "  configure:\n    volumes: *windows-backend-volumes\n",
        "  configure:\n" + windows_volume_block(provider_read_only=False),
        label="windows configure provider store",
    )
    text = replace_once(
        text,
        "  api:\n    volumes: *windows-backend-volumes\n",
        "  api:\n" + windows_volume_block(provider_read_only=False),
        label="windows api provider store",
    )
    text = replace_once(
        text,
        "  worker:\n    volumes: *windows-backend-volumes\n",
        "  worker:\n" + windows_volume_block(provider_read_only=True),
        label="windows worker provider store",
    )
    text = replace_once(
        text,
        "volumes:\n  windows_postgres:\n  windows_internal_secrets:\n",
        "volumes:\n"
        "  windows_postgres:\n"
        "  windows_internal_secrets:\n"
        "  windows_provider_secrets:\n",
        label="windows provider volume declaration",
    )
    write(path, text)


def patch_admin_page() -> None:
    path = "frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue"
    text = read(path)
    text = replace_once(
        text,
        "import VehicleMultiSelect from '../../../shared/VehicleMultiSelect.vue'\n",
        "import VehicleMultiSelect from '../../../shared/VehicleMultiSelect.vue'\n"
        "import ProviderConfigurationPanel from '../components/ProviderConfigurationPanel.vue'\n",
        label="provider panel import",
    )
    text = replace_once(
        text,
        "type Tab = 'vehicles' | 'links' | 'scheme' | 'audit'\n",
        "type Tab = 'vehicles' | 'links' | 'llm' | 'tikhub' | 'scheme' | 'audit'\n",
        label="provider tabs type",
    )
    text = replace_once(
        text,
        "  if (tab.value === 'scheme') return schemeLoading.value\n  return auditLoading.value\n",
        "  if (tab.value === 'scheme') return schemeLoading.value\n"
        "  if (tab.value === 'llm' || tab.value === 'tikhub') return false\n"
        "  return auditLoading.value\n",
        label="provider loading state",
    )
    text = replace_once(
        text,
        "  if (tab.value === 'scheme') return schemeError.value\n  return auditError.value\n",
        "  if (tab.value === 'scheme') return schemeError.value\n"
        "  if (tab.value === 'llm' || tab.value === 'tikhub') return null\n"
        "  return auditError.value\n",
        label="provider error state",
    )
    text = replace_once(
        text,
        "  if (tab.value === 'scheme') return loadSchemes()\n  await loadAudit()\n",
        "  if (tab.value === 'scheme') return loadSchemes()\n"
        "  if (tab.value === 'llm' || tab.value === 'tikhub') return\n"
        "  await loadAudit()\n",
        label="provider retry state",
    )
    text = replace_once(
        text,
        '        description="车型、词包关联与 Analysis Scheme 的唯一管理入口；所有修改、发布和回滚均写入审计。"\n',
        '        description="车型、词包、AI 模型、TikHub 与 Analysis Scheme 的统一管理入口；运行时配置保存后对新任务即时生效。"\n',
        label="admin page description",
    )
    text = replace_once(
        text,
        "          v-for=\"item in ([['vehicles', '车型目录'], ['links', '词包车型关联'], ['scheme', 'Analysis Scheme'], ['audit', '审计记录']] as const)\"\n",
        "          v-for=\"item in ([['vehicles', '车型目录'], ['links', '词包车型关联'], ['llm', 'AI 模型'], ['tikhub', 'TikHub'], ['scheme', 'Analysis Scheme'], ['audit', '审计记录']] as const)\"\n",
        label="admin provider tab buttons",
    )
    insertion = '''\n      <ProviderConfigurationPanel
        v-else-if="tab === 'llm'"
        provider-kind="llm"
      />

      <ProviderConfigurationPanel
        v-else-if="tab === 'tikhub'"
        provider-kind="collection"
      />

'''
    text = replace_once(
        text,
        "      <section\n        v-else\n        class=\"card audit-card\"\n",
        insertion + "      <section\n        v-else\n        class=\"card audit-card\"\n",
        label="provider panel mounting",
    )
    write(path, text)


def patch_docs() -> None:
    path = "backend/src/aima_ugc/modules/system/README.md"
    text = read(path)
    marker = "`provider_configs.id` 是 Provider 配置实例的稳定 UUID。"
    section = '''## Runtime Provider 配置控制面

`provider_configs` 同时承载 Collection 与 LLM 的**非敏感运行配置**。管理员配置中心是人工维护入口；API Key 只写入持久化 Provider Secret Store，数据库、HTTP 响应、审计和日志都不保存 Secret 明文，也不向前端暴露内部 `secret_ref`。

运行时采用“新任务读最新配置、已创建 Run 冻结快照”的规则：

- 新 Analysis Run 每次创建时读取当前启用的默认 LLM Provider，并冻结 Provider revision、Base URL、model、timeout/concurrency/retry 与不可变 Secret 引用；
- 新 Collection Run 冻结计划引用的 Provider 配置与相同运行参数；
- 已创建 Run、运行中任务及同 Run 的自动重试继续使用原快照，不因管理员后续修改或密钥轮换发生漂移；
- 新建/手工重跑重新读取当前数据库配置，不需要重启 API、Worker 或 Docker Compose；
- `.env` / 部署 Secret 仅用于数据库尚无对应配置时的首次 bootstrap。Internal V1 TikHub Provider 一旦存在，后续启动不得再用 `.env` 覆盖数据库事实。

持久化 Secret Store 与内部系统 Secret 分离：Linux 默认位于宿主 `${AIMA_HOST_ROOT}/shared/provider-secrets`；API 以读写方式挂载用于创建不可变 Secret 版本，Worker 只读挂载用于按 Run Snapshot 解析凭据。Windows Docker Desktop 使用独立 Docker-managed `windows_provider_secrets` volume 保持相同语义。

'''
    if "## Runtime Provider 配置控制面" not in text:
        text = replace_once(text, marker, section + marker, label="system runtime provider docs")
    write(path, text)


def add_tests() -> None:
    path = "tests/unit/system/test_runtime_provider_config.py"
    content = '''from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import SecretStr

from aima_ugc.modules.collection.run_snapshot import provider_run_snapshot
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.security import SecretFileError, read_secret_ref, write_secret_ref


def test_llm_provider_keeps_domain_style_identity_for_pricing_compatibility() -> None:
    config = ProviderConfig(
        id=uuid4(),
        provider="api.deepseek.com",
        provider_kind="llm",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-pro",
        secret_ref="llm_api_key",
        enabled=True,
        is_default=True,
    )

    assert config.provider == "api.deepseek.com"
    assert config.safe_runtime_snapshot()["provider"] == "api.deepseek.com"


def test_collection_provider_still_uses_collection_contract_identity_rules() -> None:
    with pytest.raises(ValueError):
        ProviderConfig(
            id=uuid4(),
            provider="api.tikhub.io",
            provider_kind="collection",
            display_name="TikHub",
            base_url="https://api.tikhub.io",
            secret_ref="tikhub_api_key",
            enabled=True,
        )


def test_provider_secret_writer_is_immutable(tmp_path) -> None:
    root = tmp_path / "provider-secrets"
    root.mkdir()
    reference = "providers/runtime-test/key-1.key"

    write_secret_ref(root, reference, SecretStr("first-value"))
    assert read_secret_ref(root, reference).get_secret_value() == "first-value"
    with pytest.raises(SecretFileError):
        write_secret_ref(root, reference, SecretStr("second-value"))
    assert read_secret_ref(root, reference).get_secret_value() == "first-value"


def test_collection_run_snapshot_freezes_provider_runtime_revision() -> None:
    config = ProviderConfig(
        id=uuid4(),
        provider="tikhub",
        provider_kind="collection",
        display_name="TikHub",
        base_url="https://api.tikhub.io",
        secret_ref="providers/tikhub/key-2.key",
        timeout_seconds=61,
        max_retries=4,
        max_concurrency=7,
        max_rps=3,
        revision=9,
        enabled=True,
    )

    snapshot = provider_run_snapshot(config, platform="xiaohongshu")

    assert snapshot["timeout_seconds"] == 61
    assert snapshot["max_retries"] == 4
    assert snapshot["max_concurrency"] == 7
    assert snapshot["max_rps"] == 3
    assert snapshot["revision"] == 9
    assert snapshot["secret_ref"] == "providers/tikhub/key-2.key"
'''
    write(path, content)


def main() -> None:
    run("git", "fetch", "origin", "main")
    patch_administration_contract()
    patch_administration_protocol()
    patch_administration_service()
    patch_analysis_repository()
    patch_api_routes()
    patch_provider_identity()
    patch_collection_snapshot_restore()
    patch_internal_bootstrap()
    patch_compose()
    patch_windows_compose()
    patch_admin_page()
    patch_docs()
    add_tests()

    python_files = [
        "backend/src/aima_ugc/adapters/persistence/postgres/analysis.py",
        "backend/src/aima_ugc/bootstrap/administration_http.py",
        "backend/src/aima_ugc/bootstrap/api.py",
        "backend/src/aima_ugc/bootstrap/collection_scope.py",
        "backend/src/aima_ugc/bootstrap/internal_v1.py",
        "backend/src/aima_ugc/bootstrap/runtime_config.py",
        "backend/src/aima_ugc/contracts/administration.py",
        "backend/src/aima_ugc/entrypoints/internal_v1_configure_main.py",
        "backend/src/aima_ugc/modules/administration/http.py",
        "backend/src/aima_ugc/modules/system/models.py",
        "scripts/deploy/prepare_host.py",
        "tests/unit/system/test_runtime_provider_config.py",
    ]
    run("uv", "run", "ruff", "format", *python_files)
    run("uv", "run", "ruff", "check", "--fix", *python_files)
    run("uv", "run", "python", "scripts/contracts/generate.py")
    run("npm", "run", "generate:api", cwd=ROOT / "frontend")


if __name__ == "__main__":
    main()
