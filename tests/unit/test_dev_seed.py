"""开发快照的文件边界与无副作用决策回归。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str) -> object:
    """沿用脚本测试加载方式，不修改生产包搜索路径。"""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/dev" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


snapshot = load_script("recent_snapshot")


@pytest.mark.parametrize(
    "name", ["../x", "/x", "C:/x", "a\\b", "a//b", "CON", "a/NUL.csv", "a.", "a:b", "a/../b"]
)
def test_windows_unsafe_members_are_rejected(name: str) -> None:
    """路径在 Linux 验证时也必须遵守 Windows 写入约束。"""
    with pytest.raises(snapshot.SnapshotError):
        snapshot.safe_relative(name)


def test_lfs_pointer_has_recovery_hint(tmp_path: Path) -> None:
    """指针不能被当作损坏归档或空快照静默忽略。"""
    path = tmp_path / "aima_recent30.tar.gz"
    path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 100\n")
    with pytest.raises(snapshot.SnapshotError, match="git lfs pull"):
        snapshot.inspect_archive(path)


def test_safe_chinese_workspace(tmp_path: Path) -> None:
    """项目根可以含中文与空格，storage key 仍沿用服务器约束。"""
    root = tmp_path / "开发 项目"
    root.mkdir()
    assert snapshot.safe_path(root, "raw/aa.json") == root / "raw" / "aa.json"


def test_symlink_parent_is_rejected(tmp_path: Path) -> None:
    """拒绝经过链接写入根目录之外。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "raw").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 账号没有创建 symlink 的权限")
    with pytest.raises(snapshot.SnapshotError):
        snapshot.safe_path(root, "raw/a.json")


def make_archive(tmp_path: Path, *, edit=None, extra=()) -> Path:
    """合成原服务器格式，无表头CSV及全部核心表；正文大小保持很小。"""
    import csv
    import hashlib
    import io
    import json
    import tarfile

    members = {"schema.dump": b"PGDMP-fixture"}
    tables = []
    for name in sorted(snapshot.CORE):
        data = b"1\n" if name == "contents" else b""
        path = "data/" + snapshot.selected_name(name) + ".csv"
        columns = ["id"]
        if name == "artifacts":
            columns = [
                "id",
                "storage_backend",
                "storage_status",
                "storage_key",
                "sha256",
                "byte_size",
            ]
        tables.append(
            {
                "name": name,
                "columns": columns,
                "file": path,
                "count": len(list(csv.reader(io.StringIO(data.decode())))),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        members[path] = data
    manifest = {
        "format": snapshot.FORMAT,
        "postgres_major": 18,
        "alembic_version": "20261003_0082",
        "tables": tables,
        "foreign_keys": [],
        "artifacts": [],
        "missing_artifacts": [],
        "schema_size": len(members["schema.dump"]),
        "schema_sha256": hashlib.sha256(members["schema.dump"]).hexdigest(),
    }
    if edit:
        edit(manifest, members)
    members["manifest.json"] = json.dumps(manifest).encode()
    target = tmp_path / "fixture.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        for name, data in [*members.items(), *extra]:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    return target


def test_valid_server_format_is_streamed(tmp_path: Path) -> None:
    """验证原CSV命名、格式与目录，无需真实包或数据库。"""
    path = make_archive(tmp_path)
    info = snapshot.inspect_archive(path)
    folder = tmp_path / "展开 目录"
    folder.mkdir()
    snapshot.extract_verified(path, folder, info)
    assert (folder / "schema.dump").read_bytes() == b"PGDMP-fixture"


@pytest.mark.parametrize(
    "extra",
    [
        [("SCHEMA.dump", b"x")],
        [("schema.dump", b"x")],
        [("data", b"x")],
        [("unknown.csv", b"x")],
    ],
)
def test_member_set_and_windows_collisions(tmp_path: Path, extra) -> None:
    """重复、大小写和父子冲突不能被dict/set静默吞掉。"""
    with pytest.raises(snapshot.SnapshotError):
        snapshot.inspect_archive(make_archive(tmp_path, extra=extra))


@pytest.mark.parametrize(
    "mutation", ["duplicate_table", "duplicate_column", "count", "hash", "newer", "mirror"]
)
def test_invalid_manifest_and_payload(tmp_path: Path, mutation: str) -> None:
    """非法目录、正文完整性及版本都在数据库写入之前拒绝。"""

    def edit(manifest, members):
        """分别注入独立故障，不在测试中复制生产校验。"""
        table = next(t for t in manifest["tables"] if t["name"] == "contents")
        if mutation == "duplicate_table":
            manifest["tables"].append(table.copy())
        elif mutation == "duplicate_column":
            table["columns"] = ["id", "id"]
        elif mutation == "count":
            table["count"] = 9
        elif mutation == "hash":
            members[table["file"]] = b"2\n"
        elif mutation == "newer":
            manifest["alembic_version"] = "20990101_9999"
        else:
            manifest["tables"].append(
                {
                    "name": "feishu_bitable_mirrors",
                    "columns": ["id"],
                    "file": "data/" + snapshot.selected_name("feishu_bitable_mirrors") + ".csv",
                    "count": 1,
                    "size": 2,
                    "sha256": "0" * 64,
                }
            )

    path = make_archive(tmp_path, edit=edit)
    with pytest.raises(snapshot.SnapshotError):
        info = snapshot.inspect_archive(path)
        snapshot.validate_revision(ROOT, info.manifest["alembic_version"])
        folder = tmp_path / "unpack"
        folder.mkdir()
        snapshot.extract_verified(path, folder, info)


def test_disk_full_rejects_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """空间不足时不写任何解压文件。"""
    from collections import namedtuple

    usage = namedtuple("Usage", "total used free")
    path = make_archive(tmp_path)
    info = snapshot.inspect_archive(path)
    folder = tmp_path / "unpack"
    folder.mkdir()
    monkeypatch.setattr(snapshot.shutil, "disk_usage", lambda _: usage(100, 100, 0))
    with pytest.raises(snapshot.SnapshotError, match="空间"):
        snapshot.extract_verified(path, folder, info)
    assert not list(folder.iterdir())


def test_artifact_conflict_preserves_existing_bytes(tmp_path: Path) -> None:
    """哈希不同的本地文件拒绝覆盖，原始内容保持。"""
    import hashlib
    from types import SimpleNamespace

    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "raw.json").write_bytes(b"mine")
    info = SimpleNamespace(
        manifest={
            "artifacts": [
                {
                    "storage_key": "raw.json",
                    "size": 4,
                    "sha256": hashlib.sha256(b"else").hexdigest(),
                }
            ]
        }
    )
    with pytest.raises(snapshot.SnapshotError):
        snapshot.artifact_conflicts(tmp_path, root, info)
    assert (root / "raw.json").read_bytes() == b"mine"


def load_seed():
    """使用同一加载机制解析脚本依赖，不依赖宿主脚本目录搜索路径。"""
    load_script("local_runtime")
    sys.modules["recent_snapshot"] = snapshot
    return load_script("seed_data")


seed = load_seed()


def test_fixed_target_identity_guards() -> None:
    """不能凭容器名认领远端Docker、Compose或错误挂载。"""
    import copy

    value = {
        "Name": "/" + seed.POSTGRES_CONTAINER,
        "Id": "fixed-id",
        "Config": {
            "Image": seed.POSTGRES_IMAGE,
            "Labels": {},
            "Env": ["POSTGRES_DB=aima_ugc", "POSTGRES_USER=aima_ugc"],
        },
        "State": {"Running": True},
        "Mounts": [
            {
                "Type": "volume",
                "Name": seed.POSTGRES_VOLUME,
                "Destination": seed.POSTGRES_VOLUME_TARGET,
                "RW": True,
            }
        ],
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]}},
    }
    assert seed.validate_container(value, endpoint="npipe:////./pipe/docker_engine") == "fixed-id"
    bad = copy.deepcopy(value)
    bad["Mounts"][0]["Name"] = "production-data"
    with pytest.raises(snapshot.SnapshotError):
        seed.validate_container(bad, endpoint="unix:///var/run/docker.sock")
    with pytest.raises(snapshot.SnapshotError):
        seed.validate_container(value, endpoint="tcp://example:2375")
    bad = copy.deepcopy(value)
    bad["Config"]["Labels"]["com.docker.compose.project"] = "aima"
    with pytest.raises(snapshot.SnapshotError):
        seed.validate_container(bad, endpoint="unix:///var/run/docker.sock")


def test_failure_marker_is_bound_to_actual_cluster_database() -> None:
    """同卷重建容器仍保护失败现场，重建新库不因旧marker误判。"""
    identity = {
        "container_id": "new",
        "system_identifier": "cluster",
        "database_oid": 42,
        "database": "aima_ugc",
        "user": "aima_ugc",
    }
    state = {"status": "failed", "identity": {**identity, "container_id": "old"}}
    with pytest.raises(snapshot.SnapshotError):
        seed.guard_state(state, identity)
    seed.guard_state(state, {**identity, "system_identifier": "new-cluster"})


@pytest.mark.parametrize("skip,ci", [(True, False), (False, True), (False, False)])
def test_no_snapshot_or_skipped_still_checks_shared_failure(
    tmp_path: Path, monkeypatch, skip, ci
) -> None:
    """不读取快照仍须检查共用卷的失败事实，不能从另一checkout绕过。"""
    from contextlib import nullcontext
    from types import SimpleNamespace

    paths = seed.runtime_paths(tmp_path)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    if ci:
        monkeypatch.setenv("CI", "true")
    identity = {
        "system_identifier": "cluster",
        "database_oid": 42,
        "database": "aima_ugc",
        "user": "aima_ugc",
    }
    target = SimpleNamespace(
        lock=lambda: nullcontext(None),
        identity=lambda: identity,
        read_shared_state=lambda: {"status": "failed", "identity": identity},
    )
    monkeypatch.setattr(seed, "local_target", lambda _: target)
    with pytest.raises(snapshot.SnapshotError, match="未完成"):
        seed.initialize(paths, skip=skip)


@pytest.mark.parametrize("skip", [False, True])
def test_failed_target_cannot_start_even_with_skip(tmp_path: Path, monkeypatch, skip: bool) -> None:
    """failed marker在锁内重读，跳过包不能启动半库。"""
    from contextlib import nullcontext
    from types import SimpleNamespace

    identity = {
        "system_identifier": "cluster",
        "database_oid": 42,
        "database": "aima_ugc",
        "user": "aima_ugc",
    }
    paths = seed.runtime_paths(tmp_path)
    seed.write_state(paths, {"format": seed.STATE_FORMAT, "status": "failed", "identity": identity})
    target = SimpleNamespace(lock=lambda: nullcontext(None), identity=lambda: identity)
    with pytest.raises(snapshot.SnapshotError, match="未完成"):
        seed.initialize(paths, skip=skip, target=target)


def test_existing_schema_does_not_inspect_or_restore(tmp_path: Path, monkeypatch) -> None:
    """即使contents为零，只要Schema已有对象就跳过；坏包不接触已有数据。"""
    from contextlib import nullcontext
    from types import SimpleNamespace

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    paths = seed.runtime_paths(tmp_path)
    archive = tmp_path / "devdata/seed/aima_recent30.tar.gz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"existing schema must remain")
    target = SimpleNamespace(
        lock=lambda: nullcontext(None),
        identity=lambda: {
            "system_identifier": "cluster",
            "database_oid": 42,
            "database": "aima_ugc",
            "user": "aima_ugc",
        },
        read_shared_state=lambda: None,
        empty=lambda: False,
        assert_idle=lambda _: None,
    )
    monkeypatch.setattr(snapshot, "inspect_archive", lambda _: pytest.fail("已有Schema不可恢复"))
    assert "保留" in seed.initialize(paths, target=target)


@pytest.mark.parametrize(
    "context,host,selected,allowed",
    [
        ("ssh://remote", "npipe:////./pipe/local", "remote", False),
        ("npipe:////./pipe/local", "ssh://remote", "local", True),
        ("ssh://remote", "npipe:////./pipe/local", None, True),
        ("npipe:////./pipe/local", "ssh://remote", None, False),
        ("ssh://remote", None, None, False),
        ("npipe:////./pipe/local", None, None, True),
    ],
)
def test_docker_environment_precedence_matches_cli(
    tmp_path, monkeypatch, context, host, selected, allowed
):
    """DOCKER_CONTEXT优先；检查和执行均固定到真实生效的同一端点。"""
    import json

    calls = []
    for key, value in (("DOCKER_CONTEXT", selected), ("DOCKER_HOST", host)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    def fake_docker(args, **kwargs):
        calls.append((args, kwargs.get("endpoint")))
        if args[:2] == ["context", "inspect"]:
            return json.dumps([{"Endpoints": {"docker": {"Host": context}}}]).encode()
        if args[:2] == ["volume", "inspect"]:
            return json.dumps(
                [
                    {
                        "Name": seed.POSTGRES_VOLUME,
                        "Driver": "local",
                        "Scope": "local",
                        "Options": {},
                        "Labels": {},
                    }
                ]
            ).encode()
        return b"[{}]"

    monkeypatch.setattr(seed, "docker", fake_docker)
    monkeypatch.setattr(seed, "validate_container", lambda *_args, **_kwargs: "fixed-id")
    if allowed:
        target = seed.local_target(seed.runtime_paths(tmp_path))
        expected = context if selected or not host else host
        assert target.endpoint == expected
        assert all(endpoint == expected for args, endpoint in calls if args[0] != "context")
    else:
        with pytest.raises(snapshot.SnapshotError, match="远程"):
            seed.local_target(seed.runtime_paths(tmp_path))
        assert all(args[0] == "context" for args, _ in calls)


def test_compose_and_frontend_do_not_invoke_seed() -> None:
    """恢复只有源码backend入口引用，完整Compose/Release启动不调用。"""
    for relative in (
        "compose.yaml",
        "compose.windows.yaml",
        "scripts/dev/frontend.py",
        "backend/src/aima_ugc/entrypoints/api_main.py",
        "backend/src/aima_ugc/entrypoints/worker_main.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "seed_data" not in text
    assert "devdata/seed/" in (ROOT / ".dockerignore").read_text(encoding="utf-8")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
    assert "aima_recent30.tar.gz filter=lfs" in attributes
