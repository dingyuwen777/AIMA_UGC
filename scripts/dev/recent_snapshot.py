"""读取服务器 v1 快照；Windows 与 Linux 共用唯一验证和恢复 SQL。

原格式及 COPY/FK/任务停用逻辑来自用户提供的 aima_recent30_transfer.sh。
仅用于经审查的 Git 开发快照，schema.dump 包含可执行 DDL，不能接受任意上传归档。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT = "aima-recent-content-postgresql.v1"
IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_MEMBERS = 100_000
MAX_MANIFEST = 16 * 1024 * 1024
BUFFER = 1024 * 1024
CORE = {
    "alembic_version",
    "contents",
    "content_versions",
    "comments",
    "comment_versions",
    "analysis_content_results",
    "analysis_content_label_pairs",
    "jobs",
    "artifacts",
    "vehicle_brands",
    "vehicle_models",
    "content_brand_evidence",
    "content_vehicle_evidence",
}


class SnapshotError(RuntimeError):
    """拒绝无效归档或不安全目标；错误不携带 CSV 原始行。"""


def safe_relative(name: str) -> str:
    """在所有宿主上执行同一 Windows 路径规则，拒绝规范化歧义。"""
    parts = name.split("/")
    if not parts or any(
        not SEGMENT.fullmatch(p)
        or p in {".", ".."}
        or p.endswith((".", " "))
        or p.split(".")[0].upper() in RESERVED
        for p in parts
    ):
        raise SnapshotError("快照包含不安全的 Windows 相对路径")
    return PurePosixPath(*parts).as_posix()


def safe_path(root: Path, name: str) -> Path:
    """拒绝链接/重解析路径，包括运行目录本身，不沿链接落盘。"""
    name = safe_relative(name)
    target = root / Path(name)
    for part in (target, *target.parents):
        if part.is_symlink() or part.is_junction():
            raise SnapshotError("快照目标路径包含链接或重解析目录")
    if not target.resolve().is_relative_to(root.resolve()):
        raise SnapshotError("快照目标路径逃逸")
    return target


def sha256_file(path: Path) -> str:
    """流式计算文件身份，不将大归档或 Artifact 载入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(BUFFER), b""):
            digest.update(block)
    return digest.hexdigest()


def quote(name: str) -> str:
    """只允许服务器格式的数据库标识符。"""
    if not isinstance(name, str) or not IDENT.fullmatch(name):
        raise SnapshotError("快照包含非法表或列名")
    return '"' + name + '"'


def literal(value: str) -> str:
    """生成 PostgreSQL 字符串常量，调用方只传经过约束的路径或标识符。"""
    return "'" + value.replace("'", "''") + "'"


def selected_name(table: str) -> str:
    """保持服务器导出的 CSV 文件命名规则。"""
    return "aima_selected_" + hashlib.sha1(table.encode()).hexdigest()[:18]


def _integer(value: Any) -> int:
    """拒绝布尔值、负数及非整数的长度或计数。"""
    if type(value) is not int or value < 0:
        raise SnapshotError("Manifest 大小或计数必须是非负整数")
    return value


def _file_fact(item: dict[str, Any]) -> tuple[int, str]:
    """校验文件摘要形状，防止宽松转换掩盖 Manifest 错误。"""
    size = _integer(item["size"])
    digest = item["sha256"]
    if not isinstance(digest, str) or not SHA.fullmatch(digest):
        raise SnapshotError("Manifest 文件 SHA-256 无效")
    return size, digest


@dataclass(frozen=True)
class ArchiveInfo:
    """受约束的归档目录，正文仍通过流式读取。"""

    manifest: dict[str, Any]
    files: dict[str, tuple[int, str]]
    expanded_bytes: int


def _manifest_files(manifest: dict[str, Any]) -> dict[str, tuple[int, str]]:
    """从原 v1 Manifest 构造唯一文件集合，并校验表、列与外键目录。"""
    if manifest["format"] != FORMAT:
        raise SnapshotError("不支持的快照格式")
    if type(manifest["postgres_major"]) is not int:
        raise SnapshotError("快照 PostgreSQL 版本无效")
    if not isinstance(manifest["alembic_version"], str):
        raise SnapshotError("快照 Alembic 版本无效")
    files = {
        "schema.dump": _file_fact(
            {"size": manifest["schema_size"], "sha256": manifest["schema_sha256"]}
        )
    }
    tables: dict[str, list[str]] = {}
    for table in manifest["tables"]:
        name, cols = table["name"], table["columns"]
        quote(name)
        if name in tables or not isinstance(cols, list) or not cols or len(set(cols)) != len(cols):
            raise SnapshotError("Manifest 表或列重复/为空")
        for col in cols:
            quote(col)
        tables[name] = cols
        path = safe_relative(table["file"])
        if path != "data/" + selected_name(name) + ".csv" or path in files:
            raise SnapshotError("Manifest CSV 路径不匹配或重复")
        files[path] = _file_fact(table)
        _integer(table["count"])
    if not CORE.issubset(tables):
        raise SnapshotError("快照缺少 AIMA 核心表")
    for table in manifest["tables"]:
        if (
            table["name"]
            in {"feishu_bitable_mirrors", "identity_sessions", "identity_login_states"}
            and table["count"]
        ):
            raise SnapshotError("快照包含活动镜像或认证会话；请使用不含外部活动/会话的开发快照")
    seen_fks: set[tuple[str, str]] = set()
    for fk in manifest["foreign_keys"]:
        quote(fk["name"])
        child, parent = fk["child"], fk["parent"]
        identity = (child, fk["name"])
        if identity in seen_fks or child not in tables or parent not in tables or not fk["pairs"]:
            raise SnapshotError("Manifest 外键目录无效")
        seen_fks.add(identity)
        for c, p in fk["pairs"]:
            if c not in tables[child] or p not in tables[parent]:
                raise SnapshotError("Manifest 外键列无效")
    keys: set[str] = set()
    for item in manifest["artifacts"]:
        key = safe_relative(item["storage_key"])
        if key in keys:
            raise SnapshotError("Manifest Artifact key 重复")
        keys.add(key)
        files["artifacts/" + key] = _file_fact(item)
    missing: set[str] = set()
    for item in manifest.get("missing_artifacts", []):
        key = safe_relative(item["storage_key"])
        if key in keys or key in missing:
            raise SnapshotError("Manifest 缺失 Artifact 目录冲突")
        missing.add(key)
    return files


def inspect_archive(path: Path) -> ArchiveInfo:
    """第一遍只读成员目录及有界 Manifest，验证整个文件集合及 Windows 冲突。"""
    if path.is_symlink() or not path.is_file():
        raise SnapshotError("快照不存在或不是普通文件")
    with path.open("rb") as handle:
        if handle.read(128).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise SnapshotError("当前快照是 Git LFS 指针，请在仓库运行 git lfs pull")
    seen: dict[str, int] = {}
    normalized: set[str] = set()
    parent_paths: set[str] = set()
    spelling: dict[str, str] = {}
    manifest = None
    try:
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                if len(seen) >= MAX_MEMBERS or not member.isfile():
                    raise SnapshotError("归档成员过多或含非普通文件/链接")
                name = safe_relative(member.name)
                for prefix in [
                    name,
                    *[p.as_posix() for p in PurePosixPath(name).parents if p.as_posix() != "."],
                ]:
                    previous = spelling.setdefault(prefix.casefold(), prefix)
                    if previous != prefix:
                        raise SnapshotError("归档目录存在 Windows 大小写冲突")
                folded = name.casefold()
                ancestors = [
                    p.as_posix().casefold()
                    for p in PurePosixPath(name).parents
                    if p.as_posix() != "."
                ]
                if (
                    name in seen
                    or folded in normalized
                    or folded in parent_paths
                    or any(p in normalized for p in ancestors)
                ):
                    raise SnapshotError("归档成员重复、大小写或父子路径冲突")
                seen[name] = member.size
                normalized.add(folded)
                parent_paths.update(ancestors)
                if name == "manifest.json":
                    if member.size > MAX_MANIFEST:
                        raise SnapshotError("Manifest 超过安全大小")
                    stream = archive.extractfile(member)
                    assert stream is not None
                    manifest = json.load(stream)
        if not isinstance(manifest, dict):
            raise SnapshotError("快照缺少 Manifest")
        expected = _manifest_files(manifest)
        if set(seen) != {*expected, "manifest.json"}:
            raise SnapshotError("Manifest 与归档实际文件集合不一致")
        if any(seen[name] != fact[0] for name, fact in expected.items()):
            raise SnapshotError("Manifest 文件大小与归档不一致")
        return ArchiveInfo(manifest, expected, sum(seen.values()))
    except (tarfile.TarError, EOFError, OSError, ValueError, KeyError, TypeError) as exc:
        raise SnapshotError("快照损坏或 Manifest 结构无效；未执行数据库恢复") from exc


def validate_revision(root: Path, source_revision: str) -> None:
    """仅接受当前唯一 Alembic head 的已知祖先，不伪造版本或降级。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    if len(heads) != 1 or source_revision not in {r.revision for r in scripts.walk_revisions()}:
        raise SnapshotError("快照 Alembic 版本未知或比当前代码更新；请更新代码")
    # walk_revisions 在单一 head 时正是该 head 的完整祖先链。


def _check_csv(folder: Path, info: ArchiveInfo) -> None:
    """逐行检查无表头 CSV，保留嵌入换行与原 NULL 语义，避免仅信 SHA/count。"""
    old_limit = csv.field_size_limit()
    csv.field_size_limit(256 * 1024 * 1024)
    try:
        for table in info.manifest["tables"]:
            count = 0
            with safe_path(folder, table["file"]).open("r", encoding="utf-8", newline="") as handle:
                for row in csv.reader(handle, strict=True):
                    if len(row) != len(table["columns"]):
                        raise SnapshotError(f"CSV 列数不符：{table['name']}")
                    count += 1
            if count != table["count"]:
                raise SnapshotError(f"CSV 行数不符：{table['name']}")
        _check_artifact_rows(folder, info)
    except (csv.Error, UnicodeError) as exc:
        raise SnapshotError("CSV 编码或格式无效") from exc
    finally:
        csv.field_size_limit(old_limit)


def _check_artifact_rows(folder: Path, info: ArchiveInfo) -> None:
    """校验可用本地 Artifact 事实与实际文件/显式缺失集合一致；非本地/已失效不强求文件。"""
    table = next(t for t in info.manifest["tables"] if t["name"] == "artifacts")
    present = {a["storage_key"]: a for a in info.manifest["artifacts"]}
    missing = {a["storage_key"] for a in info.manifest.get("missing_artifacts", [])}
    needed: set[str] = set()
    with safe_path(folder, table["file"]).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, fieldnames=table["columns"]):
            if row.get("storage_backend") != "local" or row.get("storage_status") not in {
                "stored",
                "linked",
            }:
                continue
            key = safe_relative(row["storage_key"])
            needed.add(key)
            if key in present:
                item = present[key]
                if row.get("sha256") != item["sha256"] or row.get("byte_size") != str(item["size"]):
                    raise SnapshotError("Artifact 数据库事实与文件 Manifest 不一致")
            elif key not in missing:
                raise SnapshotError("Artifact 缺少实际文件或显式缺失记录")
    if needed != present.keys() | missing:
        raise SnapshotError("Artifact 文件/缺失目录含未绑定的业务事实")


def extract_verified(path: Path, folder: Path, info: ArchiveInfo) -> None:
    """第二遍流式写入独占临时目录并核 SHA、CSV；不使用 tar.extractall。"""
    required = (
        info.expanded_bytes + sum(a["size"] for a in info.manifest["artifacts"]) + 512 * BUFFER
    )
    if shutil.disk_usage(folder).free < required:
        raise SnapshotError("宿主磁盘空间不足以展开快照并复制 Artifact")
    try:
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                name = safe_relative(member.name)
                if name != "manifest.json" and name not in info.files:
                    raise SnapshotError("校验后归档文件集合发生变化")
                target = safe_path(folder, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, size = hashlib.sha256(), 0
                stream = archive.extractfile(member)
                if not member.isfile() or stream is None:
                    raise SnapshotError("校验后归档成员类型发生变化")
                with target.open("xb") as out:
                    while block := stream.read(BUFFER):
                        size += len(block)
                        out.write(block)
                        digest.update(block)
                if name in info.files and (size, digest.hexdigest()) != info.files[name]:
                    raise SnapshotError("快照文件 SHA-256 或长度不符：" + name)
        _check_csv(folder, info)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise SnapshotError("快照展开失败；请检查文件完整性和可用空间") from exc


def artifact_conflicts(folder: Path, artifact_root: Path, info: ArchiveInfo) -> None:
    """数据库写入之前拒绝任何已有不同内容 Artifact，绝不覆盖用户文件。"""
    for item in info.manifest["artifacts"]:
        target = safe_path(artifact_root, item["storage_key"])
        if target.exists() and (
            not target.is_file()
            or target.stat().st_size != item["size"]
            or sha256_file(target) != item["sha256"]
        ):
            raise SnapshotError("本地 Artifact 已存在且内容不同；未执行数据库恢复")


def install_artifacts(folder: Path, artifact_root: Path, info: ArchiveInfo) -> None:
    """只原子发布不存在的文件，同内容复用；失败保留现场以供人工恢复。"""
    for item in info.manifest["artifacts"]:
        key = item["storage_key"]
        target = safe_path(artifact_root, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.stat().st_size != item["size"] or sha256_file(target) != item["sha256"]:
                raise SnapshotError("Artifact 发布期间发生同名内容冲突")
            continue
        temporary = target.with_name("." + target.name + ".seed-" + os.urandom(12).hex())
        try:
            shutil.copyfile(safe_path(folder / "artifacts", key), temporary)
            os.link(temporary, target)
        except FileExistsError:
            if sha256_file(target) != item["sha256"]:
                raise SnapshotError("Artifact 发布期间发生竞争冲突") from None
        finally:
            temporary.unlink(missing_ok=True)


def metadata_query() -> str:
    """读取当前数据库的列与 FK，而不是依赖某个历史静态表名单。"""
    return r"""
    WITH tables AS (
        SELECT c.oid, c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relispartition
    ), fks AS (
        SELECT co.conname, child.relname AS child, parent.relname AS parent,
          (SELECT jsonb_agg(jsonb_build_array(ca.attname, pa.attname) ORDER BY ord.n)
           FROM unnest(co.conkey,co.confkey) WITH ORDINALITY AS ord(ca,pa,n)
           JOIN pg_attribute ca ON ca.attrelid=co.conrelid AND ca.attnum=ord.ca
           JOIN pg_attribute pa ON pa.attrelid=co.confrelid AND pa.attnum=ord.pa) AS pairs
        FROM pg_constraint co
        JOIN pg_class child ON child.oid=co.conrelid
        JOIN pg_class parent ON parent.oid=co.confrelid
        JOIN pg_namespace cn ON cn.oid=child.relnamespace
        JOIN pg_namespace pn ON pn.oid=parent.relnamespace
        WHERE co.contype='f' AND cn.nspname='public' AND pn.nspname='public'
    )
    SELECT jsonb_build_object(
      'tables', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
         'name',t.relname,
         'columns',(SELECT jsonb_agg(a.attname ORDER BY a.attnum)
           FROM pg_attribute a WHERE a.attrelid=t.oid AND a.attnum>0
              AND NOT a.attisdropped AND a.attgenerated='')
       ) ORDER BY t.relname),'[]'::jsonb) FROM tables t),
      'fks', (SELECT COALESCE(jsonb_agg(jsonb_build_object('name',conname,
         'child',child,'parent',parent,'pairs',pairs)),'[]'::jsonb) FROM fks)
    )::text
    """


def fk_join(fk: dict[str, Any]) -> str:
    """生成复合 FK 的严格相等连接条件。"""
    return " AND ".join(f"c.{quote(child)} = p.{quote(parent)}" for child, parent in fk["pairs"])


def build_import_sql(manifest: dict[str, Any], container_data_dir: str) -> str:
    """在新库里完成 COPY、外键完整性审计与只读快照安全停机。"""
    tables = {t["name"]: t for t in manifest["tables"]}
    fks = manifest["foreign_keys"]
    parts = [
        "\\set ON_ERROR_STOP on",
        "BEGIN;",
        "SET LOCAL statement_timeout=0;",
        "SET LOCAL session_replication_role=replica;",
    ]
    for t in manifest["tables"]:
        name, cols = t["name"], t["columns"]
        if t["count"] <= 0:
            continue
        cols_sql = ", ".join(quote(x) for x in cols)
        path = f"{container_data_dir}/{t['file']}"
        parts.append(
            f"COPY public.{quote(name)} ({cols_sql}) FROM {literal(path)} "
            "WITH (FORMAT csv, NULL '\\N');"
        )
    # 原实例的 queued/running 任务不能在本地因租约过期再次被执行。
    if "jobs" in tables:
        parts.append(
            "UPDATE public.jobs SET status='cancelled', lease_owner=NULL, lease_token=NULL, "
            "lease_expires_at=NULL, finished_at=COALESCE(finished_at, now()), "
            "error_code=COALESCE(error_code,'snapshot_import_cancelled'), updated_at=now() "
            "WHERE status IN ('queued','running');"
        )
    if "collection_runs" in tables:
        parts.append(
            "UPDATE public.collection_runs SET status='cancelled',"
            "finished_at=COALESCE(finished_at,now()) "
            "WHERE status IN ('queued','running');"
        )
    if "collection_plans" in tables:
        parts.append(
            "UPDATE public.collection_plans SET enabled=false,updated_at=now() WHERE enabled=true;"
        )
    if "provider_configs" in tables:
        parts.append(
            "UPDATE public.provider_configs SET enabled=false,is_default=false,updated_at=now() "
            "WHERE enabled=true OR is_default=true;"
        )
    # 不改写 Analysis Run 的原始状态和历史结果来源：部分 Run 可能已产生成功标签。
    # 已将本地 Job 变为终态且禁用 Provider，既不会自动重新打标也不会再次采集。
    parts.append("SET LOCAL session_replication_role=origin;")
    # 所有 FK 在 replica 复制模式中未执行；显式检查每一个 FK 的每一行，拒绝不闭合快照。
    parts.append("DO $fkcheck$ BEGIN")
    for fk in fks:
        child, parent = fk["child"], fk["parent"]
        if child not in tables or parent not in tables:
            raise SnapshotError("不支持的外键关系")
        join = fk_join(fk)
        notnull = " AND ".join(f"c.{quote(col)} IS NOT NULL" for col, _ in fk["pairs"])
        fail = (
            f"SELECT 1 FROM public.{quote(child)} c WHERE {notnull} AND NOT EXISTS "
            f"(SELECT 1 FROM public.{quote(parent)} p WHERE {join}) LIMIT 1"
        )
        parts.append(
            f"IF EXISTS ({fail}) THEN RAISE EXCEPTION "
            f"{literal('内容快照外键缺失: ' + fk['name'])}; END IF;"
        )
    parts.append("END $fkcheck$;")
    parts.append("DO $counts$ BEGIN")
    for t in manifest["tables"]:
        parts.append(
            f"IF (SELECT count(*) FROM public.{quote(t['name'])}) <> {int(t['count'])} THEN "
            f"RAISE EXCEPTION {literal('快照数据行数不匹配: ' + t['name'])}; END IF;"
        )
    parts.append("END $counts$;")
    parts.append("COMMIT;")
    # 导入后重建来源数据范围内的派生筛选目录；不复制生产全库聚合计数。
    if {"voice_plaza_filter_catalog", "voice_plaza_filter_catalog_entries"}.issubset(tables):
        parts.append("BEGIN;")
        parts.append("DELETE FROM public.voice_plaza_filter_catalog;")
        parts.append(
            "INSERT INTO public.voice_plaza_filter_catalog "
            "(dimension,value,secondary_value,content_count,updated_at) "
            "SELECT dimension,value,secondary_value,count(*),now() "
            "FROM public.voice_plaza_filter_catalog_entries "
            "GROUP BY dimension,value,secondary_value;"
        )
        parts.append("COMMIT;")
    if {"voice_plaza_projection_state", "voice_plaza_content_projection", "contents"}.issubset(
        tables
    ):
        parts.append("BEGIN;")
        parts.append("DELETE FROM public.voice_plaza_projection_state;")
        parts.append(
            "INSERT INTO public.voice_plaza_projection_state "
            "(singleton,status,generation,last_content_id,projected_count,total_content_count,"
            "started_at,finished_at,last_error_code,updated_at) "
            "SELECT true,CASE WHEN (SELECT count(*) FROM public.voice_plaza_content_projection)="
            "(SELECT count(*) FROM public.contents) THEN 'ready' ELSE 'pending' END,"
            "1,NULL,(SELECT count(*) FROM public.voice_plaza_content_projection),"
            "(SELECT count(*) FROM public.contents),now(),NULL,NULL,now();"
        )
        parts.append("COMMIT;")
    # 复制显式写入的 IDENTITY/SERIAL 后，修正序列，否则本地新 Run 可能撞唯一键。
    parts.append(
        "DO $sequences$ DECLARE r record; mx bigint; BEGIN "
        "FOR r IN SELECT s.oid::regclass::text AS seq, n.nspname AS sch, "
        "t.relname AS tbl, a.attname AS col "
        "FROM pg_class s JOIN pg_depend d ON d.objid=s.oid AND d.deptype IN ('a','i') "
        "JOIN pg_class t ON t.oid=d.refobjid JOIN pg_namespace n ON n.oid=t.relnamespace "
        "JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid "
        "WHERE s.relkind='S' AND n.nspname='public' LOOP "
        "EXECUTE format('SELECT max(%I) FROM %I.%I',r.col,r.sch,r.tbl) INTO mx; "
        "IF mx IS NOT NULL THEN PERFORM setval(r.seq::regclass,mx,true); END IF; "
        "END LOOP; END $sequences$;"
    )
    return "\n".join(parts) + "\n"
