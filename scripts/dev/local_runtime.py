"""AIMA_UGC 本地源码调试的跨平台运行辅助。"""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

POSTGRES_IMAGE = "postgres:18.4"
POSTGRES_CONTAINER = "aima-ugc-postgres-dev"
POSTGRES_VOLUME = "aima-ugc-postgres-dev-data"
POSTGRES_VOLUME_TARGET = "/var/lib/postgresql"
POSTGRES_HOST = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_DB = "aima_ugc"
POSTGRES_USER = "aima_ugc"
LOCAL_TIKHUB_SECRET_REF = "tikhub_api_key"
LOCAL_LLM_SECRET_REF = "llm_api_key"

_ALLOWED_LOCAL_KEYS = frozenset(
    {
        "AIMA_TIKHUB_BASE_URL",
        "AIMA_TIKHUB_API_KEY",
        "AIMA_LLM_BASE_URL",
        "AIMA_LLM_PROVIDER_NAME",
        "AIMA_LLM_MODEL",
        "AIMA_LLM_API_KEY",
        "AIMA_HISTORICAL_IMPORT_ROOT",
        "AIMA_DEV_ENABLE_SCHEDULER",
    }
)
_RUNTIME_LLM_KEYS = (
    "AIMA_LLM_BASE_URL",
    "AIMA_LLM_PROVIDER_NAME",
    "AIMA_LLM_MODEL",
)


class LocalDevError(RuntimeError):
    """本地开发环境无法安全自动准备。"""


@dataclass(frozen=True, slots=True)
class LocalDevConfig:
    """开发者真正需要决定的可选本地能力。"""

    tikhub_base_url: str
    tikhub_api_key: str | None
    llm_base_url: str | None
    llm_provider_name: str | None
    llm_model: str | None
    llm_api_key: str | None
    historical_import_root: str | None
    scheduler_enabled: bool
    unknown_keys: tuple[str, ...]

    @property
    def tikhub_configured(self) -> bool:
        return self.tikhub_api_key is not None

    @property
    def llm_configured(self) -> bool:
        return (
            self.llm_base_url is not None
            and self.llm_model is not None
            and self.llm_api_key is not None
        )

    @property
    def llm_partially_configured(self) -> bool:
        supplied = (self.llm_base_url, self.llm_provider_name, self.llm_model, self.llm_api_key)
        return any(value is not None for value in supplied) and not self.llm_configured


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """本地运行目录；全部位于 Git 忽略的 `.runtime/`。"""

    root: Path
    runtime: Path
    data: Path
    logs: Path
    internal_secrets: Path
    external_secrets: Path
    dev_state: Path
    historical_input: Path

    @property
    def postgres_password_file(self) -> Path:
        return self.internal_secrets / "postgres_password"

    @property
    def import_cursor_key_file(self) -> Path:
        return self.internal_secrets / "import_batch_cursor_signing_key"

    @property
    def content_cursor_key_file(self) -> Path:
        return self.internal_secrets / "content_cursor_signing_key"

    @property
    def runtime_cursor_key_file(self) -> Path:
        return self.internal_secrets / "collection_runtime_cursor_signing_key"

    @property
    def tikhub_secret_file(self) -> Path:
        return self.external_secrets / LOCAL_TIKHUB_SECRET_REF

    @property
    def llm_secret_file(self) -> Path:
        return self.external_secrets / LOCAL_LLM_SECRET_REF

    @property
    def frontend_lock_fingerprint_file(self) -> Path:
        return self.dev_state / "frontend-package-lock.sha256"


def repository_root() -> Path:
    """返回仓库根；本文件固定在 `scripts/dev/`。"""

    return Path(__file__).resolve().parents[2]


def runtime_paths(root: Path) -> RuntimePaths:
    """返回源码开发运行路径，包含默认历史迁移专用根目录。"""

    runtime = root / ".runtime"
    return RuntimePaths(
        root=root,
        runtime=runtime,
        data=runtime / "data",
        logs=runtime / "logs",
        internal_secrets=runtime / "internal-secrets",
        external_secrets=runtime / "secrets",
        dev_state=runtime / "dev",
        historical_input=runtime / "historical-input",
    )


def ensure_env_local(root: Path) -> tuple[Path, bool]:
    """缺少 `env.local` 时从提交到 Git 的模板复制一份。"""

    source = root / "env.local.example"
    target = root / "env.local"
    if target.exists():
        return target, False
    if not source.is_file():
        raise LocalDevError(f"缺少本地配置模板：{source}")
    shutil.copyfile(source, target)
    return target, True


def parse_env_file(path: Path) -> dict[str, str]:
    """解析本地简单 `KEY=value` 文件；不做变量插值或命令执行。"""

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LocalDevError(f"无法读取本地配置：{path}") from exc

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise LocalDevError(f"{path}:{line_no} 必须使用 KEY=value 格式")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key or not key.replace("_", "A").isalnum() or key[0].isdigit():
            raise LocalDevError(f"{path}:{line_no} 包含非法配置名：{key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_local_dev_config(path: Path) -> LocalDevConfig:
    """从简化的 `env.local` 加载允许传入源码开发进程的配置。"""

    values = parse_env_file(path)
    unknown = tuple(sorted(key for key in values if key not in _ALLOWED_LOCAL_KEYS))
    return LocalDevConfig(
        tikhub_base_url=_clean(values.get("AIMA_TIKHUB_BASE_URL")) or "https://api.tikhub.io",
        tikhub_api_key=_clean(values.get("AIMA_TIKHUB_API_KEY")),
        llm_base_url=_clean(values.get("AIMA_LLM_BASE_URL")),
        llm_provider_name=_clean(values.get("AIMA_LLM_PROVIDER_NAME")),
        llm_model=_clean(values.get("AIMA_LLM_MODEL")),
        llm_api_key=_clean(values.get("AIMA_LLM_API_KEY")),
        historical_import_root=_clean(values.get("AIMA_HISTORICAL_IMPORT_ROOT")),
        scheduler_enabled=_parse_bool(
            values.get("AIMA_DEV_ENABLE_SCHEDULER", "false"),
            key="AIMA_DEV_ENABLE_SCHEDULER",
        ),
        unknown_keys=unknown,
    )


def prepare_runtime_directories(paths: RuntimePaths) -> None:
    """创建源码开发所需的 Git 忽略目录。"""

    for path in (
        paths.data,
        paths.logs,
        paths.internal_secrets,
        paths.external_secrets,
        paths.dev_state,
        paths.historical_input,
    ):
        path.mkdir(parents=True, exist_ok=True)


def prepare_cursor_secrets(paths: RuntimePaths) -> None:
    for path in (
        paths.import_cursor_key_file,
        paths.content_cursor_key_file,
        paths.runtime_cursor_key_file,
    ):
        ensure_random_secret(path, min_characters=48)


def ensure_random_secret(path: Path, *, min_characters: int) -> str:
    """只在缺失时生成随机 Secret；已有值不静默轮换。"""

    if path.is_symlink():
        raise LocalDevError(f"本地内部 Secret 不允许符号链接：{path}")
    if path.exists():
        value = _read_local_secret(path)
        if len(value) < min_characters:
            raise LocalDevError(
                f"本地 Secret 长度不足：{path}；请删除该本地文件后重新启动以自动生成。"
            )
        return value
    value = secrets.token_urlsafe(max(36, min_characters))
    _write_private_text(path, value)
    return value


def build_runtime_environment(
    *,
    paths: RuntimePaths,
    config: LocalDevConfig,
) -> dict[str, str]:
    """把简化 `env.local` 转换为正式进程已有的 AIMA_* + Secret File。"""

    environment = dict(os.environ)
    # Windows 安全软件可能注入不可写的全局 keylog 路径；只从本地子进程环境移除，
    # 避免 Python 初始化 TLS 时因写权限失败而让 API/Worker 意外退出。
    environment.pop("SSLKEYLOGFILE", None)
    for key in _ALLOWED_LOCAL_KEYS:
        environment.pop(key, None)
    environment.update(
        {
            "AIMA_DATA_DIR": str(paths.data),
            "AIMA_LOG_DIR": str(paths.logs),
            "AIMA_SECRET_DIR": str(paths.internal_secrets),
            "AIMA_EXTERNAL_SECRET_DIR": str(paths.external_secrets),
            "AIMA_DB_HOST": POSTGRES_HOST,
            "AIMA_DB_PORT": str(POSTGRES_PORT),
            "AIMA_DB_NAME": POSTGRES_DB,
            "AIMA_DB_USER": POSTGRES_USER,
            "AIMA_DB_CONNECT_TIMEOUT_SECONDS": "3",
        }
    )
    for key in _RUNTIME_LLM_KEYS:
        environment.pop(key, None)

    if config.historical_import_root is not None:
        environment["AIMA_HISTORICAL_IMPORT_ROOT"] = config.historical_import_root

    if config.llm_configured:
        assert config.llm_base_url is not None
        assert config.llm_model is not None
        assert config.llm_api_key is not None
        environment["AIMA_LLM_BASE_URL"] = config.llm_base_url
        environment["AIMA_LLM_MODEL"] = config.llm_model
        if config.llm_provider_name is not None:
            environment["AIMA_LLM_PROVIDER_NAME"] = config.llm_provider_name
        _write_private_text(paths.llm_secret_file, config.llm_api_key)
    else:
        _remove_if_exists(paths.llm_secret_file)

    if config.tikhub_configured:
        assert config.tikhub_api_key is not None
        _write_private_text(paths.tikhub_secret_file, config.tikhub_api_key)
    else:
        _remove_if_exists(paths.tikhub_secret_file)

    return environment


def ensure_postgres_container(paths: RuntimePaths, *, timeout_seconds: float = 60.0) -> None:
    """确保固定 PostgreSQL 18.4 本地容器已运行并 ready。"""

    docker = shutil.which("docker")
    if docker is None:
        raise LocalDevError("未找到 Docker CLI。请先安装并启动 Docker Desktop / Docker Engine。")
    _run_docker(docker, ("info", "--format", "{{.ServerVersion}}"), failure="Docker Engine 不可用")

    container = _docker_inspect(docker, "container", POSTGRES_CONTAINER)
    volume = _docker_inspect(docker, "volume", POSTGRES_VOLUME)

    if container is None:
        if volume is not None and not paths.postgres_password_file.is_file():
            raise LocalDevError(
                "发现既有本地 PostgreSQL volume，但新的内部密码文件不存在："
                f"{paths.postgres_password_file}。"
                "旧 `.runtime/secrets/postgres_password` 已不再受支持。"
                "请显式删除本地开发 volume 后重建，或把与该数据库 Role 实际匹配的密码"
                "放到新的内部路径。"
            )
        password = ensure_random_secret(paths.postgres_password_file, min_characters=32)
        docker_environment = dict(os.environ)
        docker_environment["POSTGRES_PASSWORD"] = password
        _run_docker(
            docker,
            (
                "run",
                "--detach",
                "--name",
                POSTGRES_CONTAINER,
                "--env",
                f"POSTGRES_DB={POSTGRES_DB}",
                "--env",
                f"POSTGRES_USER={POSTGRES_USER}",
                "--env",
                "POSTGRES_PASSWORD",
                "--publish",
                f"{POSTGRES_HOST}:{POSTGRES_PORT}:5432",
                "--volume",
                f"{POSTGRES_VOLUME}:{POSTGRES_VOLUME_TARGET}",
                POSTGRES_IMAGE,
            ),
            environment=docker_environment,
            failure="创建本地 PostgreSQL 容器失败",
        )
    else:
        image = _docker_field(docker, POSTGRES_CONTAINER, "{{.Config.Image}}")
        if image != POSTGRES_IMAGE:
            raise LocalDevError(
                f"本地容器 {POSTGRES_CONTAINER} 使用 {image!r}，预期 {POSTGRES_IMAGE!r}。"
                "为避免自动破坏本地数据，请人工确认后再重建该开发容器。"
            )
        if not paths.postgres_password_file.is_file():
            raise LocalDevError(
                f"本地容器 {POSTGRES_CONTAINER} 已存在，但新的内部密码文件不存在："
                f"{paths.postgres_password_file}。"
                "旧 `.runtime/secrets/postgres_password` 已不再受支持。"
                "请显式删除本地开发 container/volume 后重建，或把与该数据库 Role "
                "实际匹配的密码放到新的内部路径。"
            )
        _read_local_secret(paths.postgres_password_file)
        running = _docker_field(docker, POSTGRES_CONTAINER, "{{.State.Running}}")
        if running != "true":
            _run_docker(
                docker,
                ("start", POSTGRES_CONTAINER),
                failure="启动本地 PostgreSQL 容器失败",
            )

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                POSTGRES_CONTAINER,
                "pg_isready",
                "-U",
                POSTGRES_USER,
                "-d",
                POSTGRES_DB,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise LocalDevError(f"PostgreSQL 未在 {timeout_seconds:.0f}s 内 ready")


def stop_postgres_container() -> str:
    """停止本地 PostgreSQL 开发容器，但保留容器本身与 named volume。"""

    docker = shutil.which("docker")
    if docker is None:
        raise LocalDevError("未找到 Docker CLI。无法停止本地 PostgreSQL 容器。")
    _run_docker(docker, ("info", "--format", "{{.ServerVersion}}"), failure="Docker Engine 不可用")

    container = _docker_inspect(docker, "container", POSTGRES_CONTAINER)
    if container is None:
        return "missing"

    running = _docker_field(docker, POSTGRES_CONTAINER, "{{.State.Running}}")
    if running != "true":
        return "already_stopped"

    _run_docker(
        docker,
        ("stop", POSTGRES_CONTAINER),
        failure="停止本地 PostgreSQL 容器失败",
    )
    return "stopped"


def frontend_dependencies_stale(paths: RuntimePaths, frontend_dir: Path) -> bool:
    node_modules = frontend_dir / "node_modules"
    lock_file = frontend_dir / "package-lock.json"
    if not node_modules.is_dir() or not lock_file.is_file():
        return True
    current = sha256_file(lock_file)
    try:
        recorded = paths.frontend_lock_fingerprint_file.read_text(encoding="utf-8").strip()
    except OSError:
        return True
    return recorded != current


def record_frontend_lock_fingerprint(paths: RuntimePaths, frontend_dir: Path) -> None:
    paths.dev_state.mkdir(parents=True, exist_ok=True)
    fingerprint = sha256_file(frontend_dir / "package-lock.json")
    paths.frontend_lock_fingerprint_file.write_text(f"{fingerprint}\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_bool(value: str, *, key: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise LocalDevError(f"{key} 必须是 true/false（也接受 1/0、yes/no、on/off）")


def _write_private_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_local_secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise LocalDevError(f"无法读取本地 Secret：{path}") from exc
    if not value:
        raise LocalDevError(f"本地 Secret 为空：{path}")
    return value


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise LocalDevError(f"无法更新本地 Secret：{path}") from exc


def _docker_inspect(docker: str, kind: str, name: str) -> str | None:
    result = subprocess.run(
        [docker, f"{kind}", "inspect", name],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return None


def _docker_field(docker: str, container: str, template: str) -> str:
    result = _run_docker(
        docker,
        ("inspect", "--format", template, container),
        failure=f"读取本地容器状态失败：{container}",
    )
    return result.stdout.strip()


def _run_docker(
    docker: str,
    arguments: tuple[str, ...],
    *,
    failure: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [docker, *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise LocalDevError(f"{failure}：{detail[:500]}")
    return result
