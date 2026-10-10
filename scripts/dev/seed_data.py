"""源码开发共享快照入口；不被 API、Worker 或 Compose 生产启动调用。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
import recent_snapshot as snapshot
from local_runtime import (
    POSTGRES_CONTAINER,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_IMAGE,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_VOLUME,
    POSTGRES_VOLUME_TARGET,
    LocalDevError,
    RuntimePaths,
    repository_root,
    runtime_paths,
)

STATE_FORMAT = "aima-dev-seed-state.v1"
LOCK_KEY = 714716003
RECOVERY = (
    "请停止开发进程，查看 seed_data.py status；"
    "确认需要丢弃本地数据时执行 reset --dry-run / reset --execute。"
)


def docker(
    args: list[str], *, data: bytes | None = None, phase: str, endpoint: str | None = None
) -> bytes:
    """只通过参数数组调用 Docker；不输出可能包含原始行或凭据的 stderr。"""
    executable = shutil.which("docker")
    if executable is None:
        raise snapshot.SnapshotError("未找到 Docker CLI；请安装并启动 Docker Desktop")
    try:
        environment = os.environ.copy()
        command = [executable]
        if endpoint is not None:
            # DOCKER_CONTEXT优先于DOCKER_HOST；执行固定到已核验的同一本机daemon。
            environment.pop("DOCKER_CONTEXT", None)
            environment["DOCKER_HOST"] = endpoint
            command.extend(["--host", endpoint])
        result = subprocess.run(
            [*command, *args],
            input=data,
            capture_output=True,
            check=False,
            shell=False,
            env=environment,
        )
    except OSError as exc:
        raise snapshot.SnapshotError(f"{phase}：Docker 调用失败") from exc
    if result.returncode:
        raise snapshot.SnapshotError(
            f"{phase}失败（exit={result.returncode}）；未输出可能含敏感数据的数据库上下文。{RECOVERY}"
        )
    return result.stdout


@dataclass(frozen=True)
class DatabaseTarget:
    """恢复执行器的显式目标；公共 CLI 只由 local_target 创建固定开发目标。"""

    container: str
    database: str
    user: str
    host: str
    port: int
    password_file: Path
    container_id: str
    endpoint: str | None = None

    def command(self, args: list[str], *, phase: str) -> bytes:
        """恢复期间固定Docker端点及容器ID，不重新解析可变的context。"""
        return docker(args, phase=phase, endpoint=self.endpoint)

    def psql(self, sql: str, *, database: str | None = None) -> str:
        """使用容器内客户端，密码保留在容器环境，SQL经标准输入传递。"""
        code = (
            'export PGPASSWORD="$POSTGRES_PASSWORD"; '
            'exec psql -X -v ON_ERROR_STOP=1 -A -t -U "$1" -d "$2"'
        )
        return (
            docker(
                [
                    "exec",
                    "-i",
                    self.container_id,
                    "sh",
                    "-ec",
                    code,
                    "sh",
                    self.user,
                    database or self.database,
                ],
                data=sql.encode("utf-8"),
                phase="数据库校验/导入",
                endpoint=self.endpoint,
            )
            .decode("utf-8")
            .strip()
        )

    @contextmanager
    def lock(self) -> Iterator[psycopg.Connection[Any]]:
        """会话级排他锁随进程退出释放，导入/reset共用；不使用可遗留的 PID 锁文件。"""
        try:
            password = self.password_file.read_text(encoding="utf-8").strip()
            with psycopg.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=password,
                dbname="postgres",
                application_name="aima-dev-seed",
                autocommit=True,
                connect_timeout=5,
            ) as connection:
                locked = connection.execute(
                    "SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)
                ).fetchone()
                if not locked or not locked[0]:
                    raise snapshot.SnapshotError(
                        "另一个开发快照操作正在进行；本次不会恢复或停止数据库"
                    )
                yield connection
        except (OSError, psycopg.Error) as exc:
            raise snapshot.SnapshotError(
                "无法验证本地开发数据库连接；请检查 Docker 与内部密码文件"
            ) from exc

    def identity(self) -> dict[str, Any]:
        """同时绑定容器、集群与 DB OID；旧状态文件不能证明重建后的库成功。"""
        value = self.psql(
            "SELECT json_build_object('system_identifier', system_identifier::text, "
            "'database_oid', (SELECT oid FROM pg_database WHERE datname="
            f"{snapshot.literal(self.database)}),"
            f"'database',{snapshot.literal(self.database)},'user',current_user,"
            "'postgres_major',current_setting('server_version_num')::int / 10000) "
            "FROM pg_control_system();",
            database="postgres",
        )
        identity: dict[str, Any] = json.loads(value)
        if identity["database"] != self.database or identity["user"] != self.user:
            raise snapshot.SnapshotError("数据库实际名称/Role 与开发目标不符")
        identity["container_id"] = self.container_id
        return identity

    def shared_state_path(self) -> str:
        """PG18卷根保存共享恢复事实，不依赖任一checkout，也不新增业务表。"""
        snapshot.quote(self.database)
        return "/var/lib/postgresql/.aima-dev-seed-" + self.database + ".json"

    def read_shared_state(self) -> dict[str, Any] | None:
        """只读取固定卷内元数据；未知/损坏状态失败关闭。"""
        value = docker(
            [
                "exec",
                self.container_id,
                "sh",
                "-ec",
                'test ! -L "$1"; if test -f "$1"; then cat -- "$1"; '
                'elif test -e "$1"; then exit 1; fi',
                "sh",
                self.shared_state_path(),
            ],
            phase="读取共享恢复状态",
            endpoint=self.endpoint,
        )
        return decode_state(value.decode("utf-8")) if value else None

    def write_shared_state(self, state: dict[str, Any]) -> None:
        """先持久化共享失败/完成事实，再写checkout缓存；原子替换防止半JSON。"""
        docker(
            [
                "exec",
                "-i",
                self.container_id,
                "sh",
                "-ec",
                'test ! -L "$1"; temporary="$1.tmp-$2"; '
                "trap 'rm -f -- \"$temporary\"' EXIT; "
                '(umask 077; set -C; cat > "$temporary"); sync "$temporary"; '
                'mv -f -- "$temporary" "$1"; sync /var/lib/postgresql',
                "sh",
                self.shared_state_path(),
                uuid.uuid4().hex,
            ],
            data=json.dumps(state, ensure_ascii=False).encode("utf-8"),
            phase="保存共享恢复状态",
            endpoint=self.endpoint,
        )

    def clear_shared_state(self) -> None:
        """仅在已确认reset完成后移除本数据库的专用元数据，不触及PGDATA。"""
        docker(
            [
                "exec",
                self.container_id,
                "sh",
                "-ec",
                'test ! -L "$1"; rm -f -- "$1"; sync /var/lib/postgresql',
                "sh",
                self.shared_state_path(),
            ],
            phase="清理已完成的重置状态",
            endpoint=self.endpoint,
        )

    def empty(self) -> bool:
        """任何非系统 Schema 或 public 对象都保守视为需保护的已有数据库。"""
        count = self.psql(
            "SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
            "AND n.nspname NOT LIKE 'pg_toast%' "
            "AND n.nspname NOT LIKE 'pg_temp%') + "
            "(SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public') + "
            "(SELECT count(*) FROM pg_extension WHERE extname<>'plpgsql') + "
            "(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public') + "
            "(SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','pg_catalog',"
            "'information_schema') AND nspname NOT LIKE 'pg_toast%' "
            "AND nspname NOT LIKE 'pg_temp%');"
        )
        return int(count) == 0

    def assert_idle(self, connection: psycopg.Connection[Any]) -> None:
        """拒绝在 API/Worker/其它客户端仍连接目标库时进行恢复或 reset。"""
        row = connection.execute(
            # 大量导入后 PostgreSQL 会自动维护；它不是业务客户端，不能阻断正常重启。
            "SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid() "
            "AND backend_type<>'autovacuum worker'",
            (self.database,),
        ).fetchone()
        if row and row[0]:
            raise snapshot.SnapshotError("开发数据库仍有连接；请先停止 API/Worker/Scheduler 后重试")

    def summary(self) -> dict[str, int]:
        """只输出业务计数，不打印内容或认证信息。"""
        tables = json.loads(self.psql(snapshot.metadata_query()))["tables"]
        names = {t["name"] for t in tables}
        return {
            name: int(self.psql(f"SELECT count(*) FROM public.{snapshot.quote(name)};"))
            for name in ("contents", "comments", "analysis_content_results")
            if name in names
        }


def validate_container(value: dict[str, Any], *, endpoint: str) -> str:
    """不能因同名而认领 Compose、远端、异常卷或开放端口的容器。"""
    if not (endpoint.startswith("npipe://") or endpoint.startswith("unix://")):
        raise snapshot.SnapshotError("恢复仅允许本机 Docker context，拒绝远程 Docker")
    config = value["Config"]
    environment = dict(v.split("=", 1) for v in config.get("Env", []) if "=" in v)
    mounts = value.get("Mounts", [])
    labels = config.get("Labels") or {}
    ports = value.get("NetworkSettings", {}).get("Ports", {})
    valid = (
        value.get("Name") == "/" + POSTGRES_CONTAINER
        and config.get("Image") == POSTGRES_IMAGE
        and value.get("State", {}).get("Running") is True
        and environment.get("POSTGRES_DB") == POSTGRES_DB
        and environment.get("POSTGRES_USER") == POSTGRES_USER
        and not any(k.startswith("com.docker.compose.") for k in labels)
        and len(mounts) == 1
        and mounts[0].get("Type") == "volume"
        and mounts[0].get("Name") == POSTGRES_VOLUME
        and mounts[0].get("Destination") == POSTGRES_VOLUME_TARGET
        and mounts[0].get("RW") is True
        and ports == {"5432/tcp": [{"HostIp": POSTGRES_HOST, "HostPort": str(POSTGRES_PORT)}]}
    )
    if not valid:
        raise snapshot.SnapshotError("容器/卷/端口/Role 身份不符合固定源码开发环境；拒绝恢复或重置")
    return str(value["Id"])


def local_target(paths: RuntimePaths) -> DatabaseTarget:
    """仅从固定开发常量恢复目标，不接受 env/CLI 自行指定数据库或容器。"""
    selected = os.environ.get("DOCKER_CONTEXT")
    if selected or not os.environ.get("DOCKER_HOST"):
        context = docker(
            ["context", "inspect", *([selected] if selected else [])],
            phase="检查本机 Docker context",
        )
        endpoint = json.loads(context)[0]["Endpoints"]["docker"]["Host"]
    else:
        endpoint = os.environ["DOCKER_HOST"]
    if not (endpoint.startswith("npipe://") or endpoint.startswith("unix://")):
        raise snapshot.SnapshotError("恢复仅允许本机 Docker context，拒绝远程 Docker")
    value = json.loads(
        docker(
            ["inspect", "--type", "container", POSTGRES_CONTAINER],
            phase="检查固定开发容器",
            endpoint=endpoint,
        )
    )[0]
    container_id = validate_container(value, endpoint=endpoint)
    volume = json.loads(
        docker(["volume", "inspect", POSTGRES_VOLUME], phase="检查固定开发卷", endpoint=endpoint)
    )[0]
    if (
        volume.get("Name") != POSTGRES_VOLUME
        or volume.get("Driver") != "local"
        or volume.get("Scope") != "local"
        or volume.get("Options")
        or any(k.startswith("com.docker.compose.") for k in (volume.get("Labels") or {}))
    ):
        raise snapshot.SnapshotError("开发卷不是普通本机Docker卷，拒绝恢复或重置")
    return DatabaseTarget(
        POSTGRES_CONTAINER,
        POSTGRES_DB,
        POSTGRES_USER,
        POSTGRES_HOST,
        POSTGRES_PORT,
        paths.postgres_password_file,
        container_id,
        endpoint,
    )


def decode_state(raw: str) -> dict[str, Any]:
    """本地与卷内记录共用结构校验，不能将坏JSON当成无状态。"""
    try:
        value: dict[str, Any] = json.loads(raw)
        if value["format"] != STATE_FORMAT or value["status"] not in {
            "in_progress",
            "failed",
            "completed",
            "resetting",
        }:
            raise ValueError("invalid state")
        identity = value.get("identity")
        if not isinstance(identity, dict) or any(
            key not in identity for key in ("system_identifier", "database_oid", "database", "user")
        ):
            raise ValueError("invalid identity")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise snapshot.SnapshotError(
            "快照状态无效；请保留文件并人工检查，不能据此继续恢复"
        ) from exc


def read_state(paths: RuntimePaths) -> dict[str, Any] | None:
    """checkout缓存仅用于诊断，实际恢复归属同时从共享卷核对。"""
    path = snapshot.safe_path(paths.dev_state, "seed-state.json")
    if not path.exists():
        return None
    try:
        return decode_state(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise snapshot.SnapshotError("无法读取本地快照状态") from exc


def write_state(paths: RuntimePaths, value: dict[str, Any]) -> None:
    """先 fsync 再原子替换，进行中记录必须先于首个数据库写入。"""
    target = snapshot.safe_path(paths.dev_state, "seed-state.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def same_database(state: dict[str, Any] | None, identity: dict[str, Any]) -> bool:
    """容器重建但复用原卷时，失败现场仍属于同一数据库。"""
    previous = state.get("identity", {}) if state else {}
    keys = ("system_identifier", "database_oid", "database", "user")
    return all(previous.get(k) == identity.get(k) for k in keys)


def guard_state(state: dict[str, Any] | None, identity: dict[str, Any]) -> None:
    """只对当前目标的失败现场拦截；旧容器或已重建DB的缓存不能污染新身份。"""
    reset_missing = (
        state
        and state["status"] == "resetting"
        and identity.get("database_oid") is None
        and all(
            state.get("identity", {}).get(k) == identity.get(k)
            for k in ("system_identifier", "database", "user")
        )
    )
    if (
        state
        and (same_database(state, identity) or reset_missing)
        and state["status"] != "completed"
    ):
        raise snapshot.SnapshotError(
            "当前数据库上次快照操作未完成，禁止迁移或业务启动。" + RECOVERY
        )


@dataclass(frozen=True)
class SeedSession:
    """由启动器持有到子进程及数据库停机的共享运行租约。"""

    target: DatabaseTarget
    connection: psycopg.Connection[Any]


@contextmanager
def startup_session(
    paths: RuntimePaths, *, target: DatabaseTarget | None = None
) -> Iterator[SeedSession]:
    """启动和reset共用排他锁，不能只覆盖首次导入而漏掉Migration/运行窗口。"""
    actual = target or local_target(paths)
    with actual.lock() as connection:
        yield SeedSession(actual, connection)


def persist_state(paths: RuntimePaths, target: DatabaseTarget, state: dict[str, Any]) -> None:
    """共享事实必须先落盘；即使本机磁盘写满，其它checkout仍看得到失败保护。"""
    target.write_shared_state(state)
    write_state(paths, state)


def assert_completed(target: DatabaseTarget, state: dict[str, Any], root: Path) -> None:
    """重复启动只做数据库完整性检查，不再展开归档；允许开发者正常新增业务数据。"""
    meta = json.loads(target.psql(snapshot.metadata_query()))
    names = {t["name"] for t in meta["tables"]}
    if not snapshot.CORE.issubset(names):
        raise snapshot.SnapshotError("成功缓存对应的数据库缺少核心表，拒绝启动。" + RECOVERY)
    revision = target.psql("SELECT version_num FROM public.alembic_version;")
    snapshot.validate_revision(root, revision)
    # 校验已恢复的不可变业务主键锚点，不能只用非空库替代完成证明。
    for name, anchor in state.get("anchors", {}).items():
        column, value = anchor
        exists = target.psql(
            f"SELECT EXISTS(SELECT 1 FROM public.{snapshot.quote(name)} "
            f"WHERE {snapshot.quote(column)}::text={snapshot.literal(value)});"
        )
        if exists != "t":
            raise snapshot.SnapshotError(
                "恢复成功缓存的业务锚点已缺失；请人工核对数据库。" + RECOVERY
            )


def restore_snapshot(
    target: DatabaseTarget, folder: Path, info: snapshot.ArchiveInfo, artifact_root: Path
) -> None:
    """在已锁定且已证明空白的目标内恢复；任何阶段失败均不自动 DROP。"""
    temporary = "/tmp/aima_snapshot_" + uuid.uuid4().hex
    try:
        target.command(
            ["exec", target.container_id, "mkdir", "-m", "0700", temporary],
            phase="创建容器临时目录",
        )
        target.command(
            [
                "cp",
                str(folder / "schema.dump"),
                target.container_id + ":" + temporary + "/schema.dump",
            ],
            phase="复制 Schema",
        )
        target.command(
            ["cp", str(folder / "data"), target.container_id + ":" + temporary + "/data"],
            phase="复制 CSV",
        )
        target.command(
            ["exec", target.container_id, "chown", "-R", "postgres:postgres", temporary],
            phase="设置导入临时文件权限",
        )
        target.command(
            [
                "exec",
                target.container_id,
                "pg_restore",
                "-U",
                target.user,
                "-d",
                target.database,
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "-Fc",
                temporary + "/schema.dump",
            ],
            phase="恢复 Schema",
        )
        meta = json.loads(target.psql(snapshot.metadata_query()))
        actual_tables = {t["name"]: t["columns"] for t in meta["tables"]}
        expected_tables = {t["name"]: t["columns"] for t in info.manifest["tables"]}

        def canonical_fk(rows: list[dict[str, Any]]) -> list[str]:
            """忽略外键目录返回顺序，保留每个复合FK列序及关系身份。"""
            return sorted(json.dumps(row, sort_keys=True) for row in rows)

        if actual_tables != expected_tables or canonical_fk(meta["fks"]) != canonical_fk(
            info.manifest["foreign_keys"]
        ):
            raise snapshot.SnapshotError("恢复后的实际 Schema/列序/FK 与 Manifest 不符")
        target.psql(snapshot.build_import_sql(info.manifest, temporary))
        if (
            target.psql("SELECT version_num FROM public.alembic_version;")
            != info.manifest["alembic_version"]
        ):
            raise snapshot.SnapshotError("恢复后的 Alembic 版本与 Manifest 不符")
        if (
            target.psql("SELECT count(*) FROM public.jobs WHERE status IN ('queued','running');")
            != "0"
        ):
            raise snapshot.SnapshotError("历史快照仍含可执行任务，拒绝启动")
        snapshot.install_artifacts(folder, artifact_root, info)
    finally:
        # temporary 仅由本函数 UUID 构造，绝不接触 PGDATA 或任意用户路径。
        try:
            target.command(
                ["exec", target.container_id, "rm", "-rf", "--", temporary],
                phase="清理本次容器临时目录",
            )
        except snapshot.SnapshotError:
            print("[WARN] 本次容器快照临时目录未清理：" + temporary, file=sys.stderr)


def check_restore_space(
    target: DatabaseTarget, paths: RuntimePaths, info: snapshot.ArchiveInfo
) -> None:
    """同时核对宿主和Docker空间；Windows虚拟盘的df不能代表宿主剩余容量。"""
    host_required = info.expanded_bytes + sum(a["size"] for a in info.manifest["artifacts"])
    csv_bytes = sum(t["size"] for t in info.manifest["tables"])
    docker_required = csv_bytes * 4 + 512 * snapshot.BUFFER
    free = (
        int(
            target.command(
                [
                    "exec",
                    target.container_id,
                    "sh",
                    "-ec",
                    "df -Pk /var/lib/postgresql | tail -1 | awk '{print $4}'",
                ],
                phase="检查 Docker 存储空间",
            ).strip()
        )
        * 1024
    )
    if free < docker_required:
        raise snapshot.SnapshotError("Docker 存储空间不足以恢复 CSV、表、索引与 WAL")
    if os.name != "nt":
        return
    settings_file = Path(os.environ.get("APPDATA", "")) / "Docker/settings-store.json"
    backing: Path | None = None
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        configured = settings.get("CustomWslDistroDir")
        if isinstance(configured, str) and Path(configured).is_dir():
            backing = Path(configured)
    except OSError, ValueError:
        pass
    if backing is None:
        default = Path(os.environ.get("LOCALAPPDATA", "")) / "Docker/wsl"
        if default.is_dir():
            backing = default
    if backing is None:
        raise snapshot.SnapshotError("无法核实 Docker Desktop 虚拟盘所在宿主磁盘空间，拒绝自动恢复")
    value = json.loads(
        target.command(["inspect", target.container_id], phase="检查 Docker 数据挂载")
    )[0]
    # 正式固定开发目标使用named volume；隔离测试若数据与/tmp均bind至其它盘，仅需引擎余量。
    binds = {m["Destination"] for m in value.get("Mounts", []) if m.get("Type") == "bind"}
    required = docker_required
    if {"/var/lib/postgresql", "/tmp"}.issubset(binds):
        required = 512 * snapshot.BUFFER
    if paths.dev_state.resolve().drive.casefold() == backing.resolve().drive.casefold():
        required += host_required
    required += 512 * snapshot.BUFFER
    if shutil.disk_usage(backing).free < required:
        gib = required / (1024**3)
        raise snapshot.SnapshotError(
            f"Docker Desktop 宿主数据盘空间不足，首次恢复约需 {gib:.1f} GiB 余量；"
            "请释放空间后重试，未写入数据库"
        )


def initialize(
    paths: RuntimePaths,
    *,
    skip: bool = False,
    target: DatabaseTarget | None = None,
    session: SeedSession | None = None,
) -> str:
    """自动入口：CI/skip不读共享包；失败缓存仍执行安全检查，已有Schema绝不覆盖。"""
    archive = paths.root / "devdata/seed/aima_recent30.tar.gz"
    state = read_state(paths)
    skipped = (
        skip
        or os.environ.get("CI", "").lower() in {"true", "1"}
        or os.environ.get("GITHUB_ACTIONS") == "true"
    )
    target = session.target if session else (target or local_target(paths))
    with nullcontext(session.connection) if session else target.lock() as connection:
        state = read_state(paths)
        identity = target.identity()
        guard_state(state, identity)
        shared = target.read_shared_state()
        guard_state(shared, identity)
        artifact_root = os.path.normcase(str((paths.data / "artifacts").resolve()))
        if shared and same_database(shared, identity):
            if shared.get("artifact_root") != artifact_root:
                raise snapshot.SnapshotError(
                    "此数据库的共享快照属于另一工作目录的Artifact根；请使用原工作目录，"
                    "或停止开发进程并经确认reset后在当前目录恢复"
                )
            state = shared
        if identity.get("database_oid") is None:
            raise snapshot.SnapshotError("固定开发数据库缺失；请检查seed_data.py status并恢复reset")
        target.assert_idle(connection)
        if state and same_database(state, identity) and state["status"] == "completed":
            assert_completed(target, state, paths.root)
        if skipped or not archive.exists():
            return "已跳过共享快照" if skipped else "未提供共享快照，沿用原启动"
        digest = snapshot.sha256_file(archive)
        if not target.empty():
            changed = state and state.get("snapshot_sha256") != digest
            return (
                "共享快照已更新；保留本地数据库，需显式 reset 才能采用新版"
                if changed
                else "已有应用 Schema/数据，保留本地数据库"
            )
        target.assert_idle(connection)
        info = snapshot.inspect_archive(archive)
        if identity["postgres_major"] != info.manifest["postgres_major"]:
            raise snapshot.SnapshotError("快照与本地 PostgreSQL 主版本不一致")
        snapshot.validate_revision(paths.root, info.manifest["alembic_version"])
        paths.dev_state.mkdir(parents=True, exist_ok=True)
        check_restore_space(target, paths, info)
        with tempfile.TemporaryDirectory(prefix="seed-", dir=paths.dev_state) as temp:
            folder = Path(temp)
            print("[INFO] 校验共享快照文件/CSV/Artifact，首次恢复可能需要数分钟")
            snapshot.extract_verified(archive, folder, info)
            if snapshot.sha256_file(archive) != digest:
                raise snapshot.SnapshotError("校验期间共享快照发生变化")
            snapshot.artifact_conflicts(folder, paths.data / "artifacts", info)
            # 容器临时CSV、实际表/index/WAL与Artifact独立检查，不只检查压缩文件大小。
            check_restore_space(target, paths, info)
            # 长时间校验之后重读目标与活跃连接，防止复用过期的空库判断。
            if target.identity() != identity or not target.empty():
                raise snapshot.SnapshotError("校验期间目标数据库发生变化，拒绝写入")
            target.assert_idle(connection)
            state = {
                "format": STATE_FORMAT,
                "snapshot_format": snapshot.FORMAT,
                "snapshot_sha256": digest,
                "database": target.database,
                "container": target.container,
                "identity": identity,
                "status": "in_progress",
                "artifact_root": artifact_root,
            }
            persist_state(paths, target, state)
            try:
                restore_snapshot(target, folder, info, paths.data / "artifacts")
                state["anchors"] = {}
                for name in ("contents", "comments", "analysis_content_results"):
                    value = target.psql(
                        f"SELECT id::text FROM public.{snapshot.quote(name)} ORDER BY id LIMIT 1;"
                    )
                    if value:
                        state["anchors"][name] = ["id", value]
                state["status"] = "completed"
                state["imported_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
                state["missing_artifacts"] = len(info.manifest.get("missing_artifacts", []))
                persist_state(paths, target, state)
            except BaseException:
                state["status"] = "failed"
                persist_state(paths, target, state)
                raise
    return "共享快照恢复完成，历史任务已取消，继续正常 Migration"


def status(paths: RuntimePaths) -> None:
    """只读查询文件及真实数据库状态，不启动容器、不做Migration或恢复。"""
    archive = paths.root / "devdata/seed/aima_recent30.tar.gz"
    state = read_state(paths)
    output: dict[str, Any] = {"archive_exists": archive.is_file(), "state": state}
    if archive.is_file():
        info = snapshot.inspect_archive(archive)
        digest = snapshot.sha256_file(archive)
        output.update(
            snapshot_sha256=digest,
            snapshot_format=info.manifest["format"],
            source_revision=info.manifest["alembic_version"],
            changed=bool(state and state.get("snapshot_sha256") != digest),
        )
    target = local_target(paths)
    identity = target.identity()
    output.update(actual_identity=identity, shared_state=target.read_shared_state())
    output.update(
        counts=target.summary() if identity["database_oid"] is not None else {},
        empty_schema=target.empty() if identity["database_oid"] is not None else None,
    )
    output["state_matches_database"] = bool(
        state and state.get("identity") == output["actual_identity"]
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


def reset(paths: RuntimePaths, *, execute: bool) -> None:
    """仅确认后重建固定开发DB；不删卷、Secret或任何Artifact，未知文件保留。"""
    target = local_target(paths)
    with target.lock() as connection:
        identity = target.identity()
        shared = target.read_shared_state()
        cached = read_state(paths)
        pending = next((s for s in (shared, cached) if s and s["status"] == "resetting"), None)
        missing = identity["database_oid"] is None
        if pending and not same_database(pending, identity):
            same_cluster = all(
                pending["identity"].get(k) == identity.get(k)
                for k in ("system_identifier", "database", "user")
            )
            if not missing or not same_cluster:
                raise snapshot.SnapshotError(
                    "reset现场与当前数据库身份不符，保护陌生重建的数据库；请人工核对"
                )
        if missing and not pending:
            raise snapshot.SnapshotError("数据库缺失且无可靠reset归属，拒绝自行创建")
        target.assert_idle(connection)
        print(
            json.dumps(
                {
                    "database": target.database,
                    "container": target.container,
                    "counts": target.summary() if not missing else {},
                    "reset_phase": pending.get("reset_phase") if pending else None,
                    "artifacts": "全部保留；同内容可复用，冲突时需人工核对",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if not execute:
            print("[DRY-RUN] 未执行数据库写入")
            return
        if (
            input("此操作会丢弃本地 aima_ugc 业务数据。请输入 RESET aima_ugc：").strip()
            != "RESET aima_ugc"
        ):
            raise snapshot.SnapshotError("确认词不匹配；未执行重置")
        if local_target(paths) != target or target.identity() != identity:
            raise snapshot.SnapshotError("确认期间目标身份变化；未执行重置")
        target.assert_idle(connection)
        if pending and pending.get("reset_phase") == "created" and not missing:
            if not target.empty():
                raise snapshot.SnapshotError("已重建库出现新数据，保护当前数据库；请人工核对")
            target.clear_shared_state()
            (paths.dev_state / "seed-state.json").unlink(missing_ok=True)
            print("[OK] 已确认上次重建完成并清理状态；可运行原backend.py恢复共享快照")
            return
        value = {
            "format": STATE_FORMAT,
            "database": target.database,
            "container": target.container,
            "identity": identity,
            "status": "resetting",
            "reset_phase": "drop_pending",
        }
        persist_state(paths, target, value)
        if not missing:
            target.psql(f"DROP DATABASE {snapshot.quote(target.database)};", database="postgres")
        absent_identity = target.identity()
        if absent_identity["database_oid"] is not None or any(
            absent_identity.get(k) != identity.get(k)
            for k in ("system_identifier", "database", "user")
        ):
            # 外部客户端不一定遵守本工具锁，不能认领DROP后出现的陌生新OID。
            raise snapshot.SnapshotError(
                "DROP后出现陌生数据库或集群身份变化，保留原reset归属并拒绝继续"
            )
        value.update(identity=absent_identity, reset_phase="absent")
        persist_state(paths, target, value)
        target.psql(
            f"CREATE DATABASE {snapshot.quote(target.database)} "
            f"OWNER {snapshot.quote(target.user)};",
            database="postgres",
        )
        value.update(identity=target.identity(), reset_phase="created")
        persist_state(paths, target, value)
        target.clear_shared_state()
        (paths.dev_state / "seed-state.json").unlink(missing_ok=True)
        print("[OK] 固定开发数据库已重建；运行原 backend.py 命令恢复当前共享快照")


def main() -> int:
    """维护CLI不读取env配置，目标始终由固定源码开发常量确定。"""
    parser = argparse.ArgumentParser(description="AIMA 共享开发快照维护")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("verify")
    reset_parser = sub.add_parser("reset")
    flags = reset_parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--dry-run", action="store_true")
    flags.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    paths = runtime_paths(repository_root())
    try:
        if args.command == "verify":
            archive = paths.root / "devdata/seed/aima_recent30.tar.gz"
            info = snapshot.inspect_archive(archive)
            snapshot.validate_revision(paths.root, info.manifest["alembic_version"])
            paths.dev_state.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="verify-seed-", dir=paths.dev_state) as temp:
                snapshot.extract_verified(archive, Path(temp), info)
            print(
                json.dumps(
                    {
                        "verified": True,
                        "sha256": snapshot.sha256_file(archive),
                        "tables": len(info.manifest["tables"]),
                        "artifacts": len(info.manifest["artifacts"]),
                        "missing_artifacts": len(info.manifest.get("missing_artifacts", [])),
                    }
                )
            )
        elif args.command == "status":
            status(paths)
        else:
            reset(paths, execute=args.execute)
        return 0
    except (snapshot.SnapshotError, LocalDevError, KeyboardInterrupt) as exc:
        print(
            "[ERROR] " + (str(exc) or "操作已中断；未完成时禁止业务启动。") + " " + RECOVERY,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
