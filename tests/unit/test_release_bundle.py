from __future__ import annotations

import codecs
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "release" / "release_bundle.py"
POWERSHELL = ROOT / "scripts" / "release" / "build_local_release.ps1"


def test_catalog_reset_script_parses_in_linux_bash() -> None:
    bash = shutil.which("bash")
    if bash is None or sys.platform == "win32":
        pytest.skip("Bash 语法在 Linux CI 校验")
    subprocess.run(
        [bash, "-n", str(ROOT / "scripts" / "deploy" / "reset_keep_vehicle_catalog.sh")],
        check=True,
        capture_output=True,
        text=True,
    )


def _load_module():
    """按仓库路径加载 Release Bundle 脚本，避免把 scripts 变成生产包。"""
    spec = importlib.util.spec_from_file_location("aima_release_bundle", CORE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_profiles_keep_local_china_and_github_official_boundaries() -> None:
    module = _load_module()

    assert module.SOURCE_PROFILES["china"] == {
        "debian": "https://mirrors.aliyun.com/debian",
        "debian_security": "https://mirrors.aliyun.com/debian-security",
        "pypi": "https://mirrors.aliyun.com/pypi/simple",
        "npm": "https://registry.npmmirror.com",
    }
    assert module.SOURCE_PROFILES["official"] == {
        "debian": "http://deb.debian.org/debian",
        "debian_security": "http://deb.debian.org/debian-security",
        "pypi": "https://pypi.org/simple",
        "npm": "https://registry.npmjs.org",
    }


def test_local_and_formal_version_contracts_are_distinct() -> None:
    module = _load_module()

    module.validate_version("local-20260915", formal=False)
    module.validate_version("v3.2.0", formal=True)
    with pytest.raises(module.ReleaseBundleError):
        module.validate_version("local-20260915", formal=True)
    with pytest.raises(module.ReleaseBundleError):
        module.validate_version("bad/version", formal=False)


def test_formal_checkout_requires_clean_latest_main(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *arguments: str) -> str:
        values = {
            ("status", "--porcelain"): "",
            ("branch", "--show-current"): "main",
            ("rev-parse", "HEAD"): "abc123",
            ("rev-parse", "refs/remotes/origin/main"): "abc123",
        }
        return values[arguments]

    def fake_run(arguments, *, cwd: Path, capture: bool = False) -> str:
        del cwd, capture
        calls.append(tuple(arguments))
        return ""

    monkeypatch.setattr(module, "_require_tool", lambda _name: None)
    monkeypatch.setattr(module, "_git", fake_git)
    monkeypatch.setattr(module, "_run", fake_run)

    assert module.validate_formal_checkout(Path(".")) == "abc123"
    assert ("git", "fetch", "--quiet", "origin", "main") in calls


def test_formal_checkout_fails_when_origin_main_has_moved(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    def fake_git(_root: Path, *arguments: str) -> str:
        values = {
            ("status", "--porcelain"): "",
            ("branch", "--show-current"): "main",
            ("rev-parse", "HEAD"): "old",
            ("rev-parse", "refs/remotes/origin/main"): "new",
        }
        return values[arguments]

    monkeypatch.setattr(module, "_require_tool", lambda _name: None)
    monkeypatch.setattr(module, "_git", fake_git)
    monkeypatch.setattr(module, "_run", lambda *_args, **_kwargs: "")

    with pytest.raises(module.ReleaseBundleError, match="origin/main"):
        module.validate_formal_checkout(Path("."))


def test_build_images_adds_latest_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    calls: list[tuple[str, ...]] = []

    def fake_run(
        arguments, *, cwd: Path, capture: bool = False, env: dict[str, str] | None = None
    ) -> str:
        del cwd, env
        normalized = tuple(str(item) for item in arguments)
        calls.append(normalized)
        if normalized[:4] == ("docker", "image", "inspect", "-f") and capture:
            return "sha256:application\n"
        return ""

    monkeypatch.setattr(module, "_require_tool", lambda _name: None)
    monkeypatch.setattr(module, "_run", fake_run)

    module.build_images(Path("."), "v3.2.0", "official")

    assert (
        "docker",
        "tag",
        "aima-ugc-backend:v3.2.0",
        "aima-ugc-backend:latest",
    ) in calls
    assert (
        "docker",
        "tag",
        "aima-ugc-frontend:v3.2.0",
        "aima-ugc-frontend:latest",
    ) in calls


def test_bundle_uses_latest_runtime_alias_and_saves_both_application_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / "compose.windows.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / "env.production.example").write_text("AIMA_IMAGE_TAG=internal-v1a\n", encoding="utf-8")
    deploy_scripts = root / "scripts" / "deploy"
    deploy_scripts.mkdir(parents=True)
    for name in ("start_compose.py", "stop_compose.py"):
        (deploy_scripts / name).write_text("# deployment entry\n", encoding="utf-8")
    (deploy_scripts / "reset_keep_vehicle_catalog.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    calls: list[tuple[str, ...]] = []

    def fake_run(arguments, *, cwd: Path, capture: bool = False) -> str:
        del cwd, capture
        normalized = tuple(str(item) for item in arguments)
        calls.append(normalized)
        if normalized[:3] == ("docker", "save", "-o"):
            Path(normalized[3]).write_bytes(b"images")
        return ""

    monkeypatch.setattr(module, "_run", fake_run)
    facts = module.ImageFacts(
        backend_id="sha256:backend",
        frontend_id="sha256:frontend",
        postgres_ref="postgres@sha256:postgres",
        alembic_head="head123",
        openapi_sha256="openapi123",
    )
    bundle = tmp_path / "release-bundle"
    archive = tmp_path / "AIMA_UGC-v3.2.0-deploy.tar.gz"

    module.build_bundle_files(
        root=root,
        bundle_dir=bundle,
        archive_path=archive,
        version="v3.2.0",
        repository="dingyuwen777/AIMA_UGC",
        git_sha="abc123",
        profile_name="official",
        builder_context="github-actions",
        facts=facts,
        offline_replay=False,
        strict_replay=False,
    )

    assert "AIMA_IMAGE_TAG=latest\n" in (bundle / "env.production.example").read_text(
        encoding="utf-8"
    )
    assert (bundle / "compose.windows.yaml").is_file()
    save_call = next(call for call in calls if call[:3] == ("docker", "save", "-o"))
    assert save_call[4:] == (
        "aima-ugc-backend:v3.2.0",
        "aima-ugc-backend:latest",
        "aima-ugc-frontend:v3.2.0",
        "aima-ugc-frontend:latest",
        "postgres:18.4",
    )
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "v3.2.0"
    assert manifest["images"]["backend"]["offline_tag"] == "aima-ugc-backend:v3.2.0"
    assert manifest["images"]["frontend"]["offline_tag"] == "aima-ugc-frontend:v3.2.0"


def test_strict_replay_removes_version_and_latest_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    bundle = tmp_path / "release-bundle"
    bundle.mkdir()
    smoke_parent = tmp_path / "smoke"
    smoke_parent.mkdir()
    smoke_root = smoke_parent / "root"
    calls: list[tuple[str, ...]] = []

    class FakeCompletedProcess:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

    def fake_run(
        arguments, *, cwd: Path, capture: bool = False, env: dict[str, str] | None = None
    ) -> str:
        del cwd, env
        normalized = tuple(str(item) for item in arguments)
        calls.append(normalized)
        if normalized[:5] == ("docker", "compose", "ps", "-a", "-q"):
            return f"{normalized[-1]}-container\n"
        if normalized[:4] == ("docker", "inspect", "-f", "{{.State.ExitCode}}"):
            return "0\n"
        if normalized[:3] == ("docker", "image", "inspect") and capture:
            return "sha256:application\n"
        if normalized[:3] == ("docker", "compose", "up"):
            (smoke_root / "postgres" / "18" / "docker").mkdir(parents=True)
            log_dir = smoke_root / "runtime" / "logs"
            log_dir.mkdir(parents=True)
            (log_dir / "api.log").write_text("ready\n", encoding="utf-8")
        return ""

    def fake_subprocess_run(arguments, **_kwargs):
        if list(arguments)[:3] == ["docker", "image", "inspect"]:
            return FakeCompletedProcess(1)
        return FakeCompletedProcess(0)

    def fake_smoke_env(**_kwargs) -> Path:
        env_path = smoke_parent / "smoke.env"
        env_path.write_text("AIMA_IMAGE_TAG=latest\n", encoding="utf-8")
        return env_path

    monkeypatch.setattr(module, "verify_bundle", lambda _bundle: None)
    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix: str(smoke_parent))
    monkeypatch.setattr(module, "_find_free_port", lambda: 49152)
    monkeypatch.setattr(
        module,
        "_find_free_smoke_network",
        lambda _root: ("10.254.254.0/24", "10.254.254.1"),
    )
    monkeypatch.setattr(module, "_smoke_env", fake_smoke_env)
    monkeypatch.setattr(module, "_compose_command", lambda **_kwargs: ["docker", "compose"])
    monkeypatch.setattr(module, "_http_get", lambda _url: None)
    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module.subprocess, "run", fake_subprocess_run)

    module.replay_bundle(root=tmp_path, bundle_dir=bundle, version="v3.2.0", strict_replay=True)

    assert (
        "docker",
        "image",
        "rm",
        "aima-ugc-backend:v3.2.0",
        "aima-ugc-backend:latest",
        "aima-ugc-frontend:v3.2.0",
        "aima-ugc-frontend:latest",
        "postgres:18.4",
    ) in calls
    assert ("docker", "load", "-i", str(bundle / "images.tar")) in calls
    if os.name != "nt":
        assert (
            "bash",
            str(bundle / "reset_keep_vehicle_catalog.sh"),
            "--env-file",
            str(smoke_parent / "smoke.env"),
            "--execute",
            "--yes",
        ) in calls


def test_manifest_records_profile_upstreams_and_verification_state() -> None:
    module = _load_module()
    facts = module.ImageFacts(
        backend_id="sha256:backend",
        frontend_id="sha256:frontend",
        postgres_ref="postgres@sha256:postgres",
        alembic_head="head123",
        openapi_sha256="openapi123",
    )

    manifest = module._release_manifest(
        version="local-20260915",
        repository="dingyuwen777/AIMA_UGC",
        git_sha="abc123",
        profile_name="china",
        builder_context="local",
        facts=facts,
        offline_replay=False,
        strict_replay=False,
    )

    assert manifest["platform"] == "linux/amd64"
    assert manifest["build_source_profile"] == "china"
    assert manifest["build_upstreams"]["pypi"] == "https://mirrors.aliyun.com/pypi/simple"
    assert manifest["verification"] == {"offline_replay": False, "strict_replay": False}
    assert manifest["publication"] == {"github_release": False, "ghcr": False}


def test_smoke_network_avoids_existing_docker_subnet(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    def fake_run(arguments, *, cwd: Path, capture: bool = False) -> str:
        del cwd, capture
        if arguments == ["docker", "network", "ls", "--quiet"]:
            return "network-1\n"
        if arguments == ["docker", "network", "inspect", "network-1"]:
            return json.dumps(
                [
                    {
                        "IPAM": {
                            "Config": [
                                {"Subnet": "10.254.255.0/24", "Gateway": "10.254.255.1"},
                                {"Subnet": "fd00::/64", "Gateway": "fd00::1"},
                            ]
                        }
                    }
                ]
            )
        raise AssertionError(arguments)

    monkeypatch.setattr(module, "_run", fake_run)

    assert module._find_free_smoke_network(Path(".")) == ("10.254.254.0/24", "10.254.254.1")


def test_smoke_env_overrides_default_network(tmp_path: Path) -> None:
    module = _load_module()
    bundle = tmp_path / "release-bundle"
    bundle.mkdir()
    (bundle / "env.production.example").write_bytes((ROOT / "env.production.example").read_bytes())
    smoke_root = tmp_path / "root"
    smoke_root.mkdir()

    env_path = module._smoke_env(
        bundle_dir=bundle,
        smoke_root=smoke_root,
        port=49152,
        subnet="10.254.254.0/24",
        gateway="10.254.254.1",
    )
    values = dict(
        line.split("=", 1)
        for line in env_path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )

    assert values["AIMA_DOCKER_SUBNET"] == "10.254.254.0/24"
    assert values["AIMA_DOCKER_GATEWAY"] == "10.254.254.1"
    assert values["AIMA_HTTP_PORT"] == "49152"


def test_http_smoke_uses_direct_local_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    events: list[tuple[object, ...]] = []

    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            events.append(("read",))
            return b"ok"

    class FakeConnection:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            events.append(("connect", host, port, timeout))

        def request(self, method: str, path: str) -> None:
            events.append(("request", method, path))

        def getresponse(self) -> FakeResponse:
            return FakeResponse()

        def close(self) -> None:
            events.append(("close",))

    monkeypatch.setattr(module, "HTTPConnection", FakeConnection)

    module._http_get("http://127.0.0.1:49152/health/ready?probe=1")

    assert events == [
        ("connect", "127.0.0.1", 49152, 5),
        ("request", "GET", "/health/ready?probe=1"),
        ("read",),
        ("close",),
    ]


def test_bundle_checksum_archive_and_publication_finalization(tmp_path: Path) -> None:
    module = _load_module()
    bundle = tmp_path / "release-bundle"
    bundle.mkdir()
    for name in module.CHECKSUM_TARGETS:
        path = bundle / name
        if name == "release-manifest.json":
            path.write_text(
                json.dumps(
                    {
                        "version": "v3.2.0",
                        "git_sha": "abc123",
                        "build_source_profile": "official",
                        "verification": {"offline_replay": True, "strict_replay": True},
                        "images": {
                            "backend": {"registry_ref": None},
                            "frontend": {"registry_ref": None},
                        },
                        "publication": {"github_release": False, "ghcr": False},
                    }
                ),
                encoding="utf-8",
            )
        else:
            path.write_text(f"{name}\n", encoding="utf-8")

    module.write_bundle_checksums(bundle)
    module.verify_bundle(bundle)
    module.verify_manifest_identity(
        bundle,
        expected_version="v3.2.0",
        expected_git_sha="abc123",
        expected_profile="official",
        require_offline_replay=True,
        require_strict_replay=True,
    )

    archive = tmp_path / "AIMA_UGC-v3.2.0-deploy.tar.gz"
    module.create_archive(bundle, archive)
    with tarfile.open(archive, "r:gz") as stream:
        assert set(stream.getnames()) == module.EXPECTED_BUNDLE_ENTRIES

    module.finalize_publication(
        bundle_dir=bundle,
        archive_path=archive,
        backend_registry_ref="ghcr.io/example/backend@sha256:1",
        frontend_registry_ref="ghcr.io/example/frontend@sha256:2",
    )
    published = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    assert published["images"]["backend"]["registry_ref"].endswith("@sha256:1")
    assert published["images"]["frontend"]["registry_ref"].endswith("@sha256:2")
    assert published["publication"] == {
        "github_release": True,
        "ghcr": True,
        "ghcr_visibility": "private",
    }
    module.verify_bundle(bundle)


def test_windows_entry_defaults_to_china_and_delegates_to_shared_core() -> None:
    assert POWERSHELL.is_file()
    assert POWERSHELL.read_bytes().startswith(codecs.BOM_UTF8)
    script = POWERSHELL.read_text(encoding="utf-8")

    assert '[string]$SourceProfile = "china"' in script
    assert '[ValidateSet("china", "official")]' in script
    assert "[switch]$Verify" in script
    assert "[switch]$Formal" in script
    assert "scripts\\release\\release_bundle.py" in script
    assert '"--builder-context", "local"' in script
    assert '"--source-profile", $SourceProfile' in script
    assert '"--formal"' in script
    assert '"--verify"' in script
    assert "$pythonCommand = @(Resolve-PythonCommand)" in script
    assert "docker tag" not in script
    assert "git tag" not in script
    assert "git push" not in script
    assert "gh release" not in script
    assert "docker push" not in script
