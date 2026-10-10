"""验证启动凭据隔离、文件安全和真实配置消费者。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from aima_ugc.bootstrap.feishu_config_input import (
    CONNECTORS_FILENAME,
    FeishuConfigInputError,
    materialize_feishu_config,
    parse_feishu_config_input,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.security.secrets import read_secret_ref


def connector(code: str = "a", **overrides: object) -> dict[str, object]:
    """构造独立应用配置，凭据仅使用测试值。"""
    return {
        "code": code,
        "display_name": "企业",
        "app_id": f"cli_{code}",
        "app_secret": f"fixture-{code}-credential",
        "admin_group_id": "admin",
        "user_group_id": "user",
        "redirect_uri": f"https://ugc.example.com/api/v1/auth/feishu/{code}/callback",
        **overrides,
    }


def test_materialization_rotation_and_runtime_settings_consumer(tmp_path: Path) -> None:
    """文件更新后真实 Settings/Secret reader 按应用读取，manifest 不含凭据。"""
    for value in ("fixture-initial", "fixture-rotated"):
        config = parse_feishu_config_input(
            json.dumps([connector(app_secret=value), connector("b")])
        )
        assert value not in repr(config)
        materialize_feishu_config(tmp_path, config, write_manifest=True)
        settings = load_settings(
            {"AIMA_FEISHU_CONNECTORS_FILE": str(tmp_path / CONNECTORS_FILENAME)}
        )
        assert settings.feishu_connectors is not None
        for code, expected in (("a", value), ("b", "fixture-b-credential")):
            entry = settings.feishu_connectors.get(code)
            assert entry is not None
            assert read_secret_ref(tmp_path, entry.app_secret_ref).get_secret_value() == expected
        assert value not in (tmp_path / CONNECTORS_FILENAME).read_text()
        assert value not in repr(settings)
    if os.name == "posix":
        assert (tmp_path / "feishu_a_secret").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("value", [None, ""])
def test_manual_file_and_empty_login_manifest(tmp_path: Path, value: object) -> None:
    """缺省凭据保留手工文件，清空登录数组不会把报告应用当成登录应用。"""
    secret = tmp_path / "manual"
    secret.write_text("fixture-manual", encoding="utf-8")
    config = parse_feishu_config_input(
        json.dumps([connector(app_secret=value, app_secret_ref="manual")])
    )
    materialize_feishu_config(tmp_path, config, write_manifest=True)
    assert secret.read_text() == "fixture-manual"
    materialize_feishu_config(tmp_path, parse_feishu_config_input(""), write_manifest=True)
    settings = load_settings(
        {
            "AIMA_FEISHU_CONNECTORS_FILE": str(tmp_path / CONNECTORS_FILENAME),
            "AIMA_FEISHU_APP_ID": "cli_report",
        }
    )
    assert settings.feishu_connectors is None
    assert settings.feishu_app_id == "cli_report"


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_secret_ref": "../escaped"},
        {"app_secret_ref": "C:\\escaped"},
        {"app_secret_ref": "/escaped"},
        {"app_secret_ref": "tikhub_api_key"},
        {"app_secret_ref": CONNECTORS_FILENAME},
        {"app_secret": "bad\nsecret"},
        {"app_secret": "bad\x00secret"},
        {"app_secret": " bad "},
        {"app_secret": 5},
        {"user_group_id": "admin"},
        {"unknown": "fixture-sensitive"},
        {"redirect_uri": "https://ugc.example.com/api/v1/auth/feishu/b/callback"},
    ],
)
def test_invalid_inputs_fail_without_leaking_values(overrides: dict[str, object]) -> None:
    """校验报错不回显整个 Connector 或原始字段值。"""
    raw = json.dumps([connector(**overrides)])
    with pytest.raises(FeishuConfigInputError) as error:
        parse_feishu_config_input(raw)
    assert "fixture" not in str(error.value)
    assert raw not in str(error.value)


@pytest.mark.parametrize(
    "raw",
    [
        '[{"app_secret":"fixture-sensitive","app_secret":"other"}]',
        '[{"app_secret":"fixture-sensitive",]',
        "[]",
        "{}",
        json.dumps([connector(), connector()]),
        json.dumps(
            [connector(app_secret_ref="nested"), connector("b", app_secret_ref="nested/child")]
        ),
        json.dumps([connector(), connector("b", app_id="cli_a")]),
    ],
)
def test_invalid_json_and_cross_application_conflicts_are_rejected(raw: str) -> None:
    """重复字段/身份及文件与父目录冲突在写入前失败。"""
    with pytest.raises(FeishuConfigInputError) as error:
        parse_feishu_config_input(raw)
    assert "fixture" not in str(error.value)


def test_all_targets_are_checked_before_first_secret_is_written(tmp_path: Path) -> None:
    """后项是目录时，前项也不能被创建。"""
    (tmp_path / "feishu_b_secret").mkdir()
    config = parse_feishu_config_input(json.dumps([connector(), connector("b")]))
    with pytest.raises(FeishuConfigInputError):
        materialize_feishu_config(tmp_path, config)
    assert not (tmp_path / "feishu_a_secret").exists()


def test_business_process_rejects_unprocessed_plaintext_input() -> None:
    """绕过 launcher 不能让业务 Settings 悄悄保留明文凭据。"""
    with pytest.raises(ValueError) as error:
        load_settings({"AIMA_FEISHU_CONNECTORS": json.dumps([connector()])})
    assert "fixture-a-credential" not in str(error.value)
    assert "bootstrap" in str(error.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows 文件名等价语义")
@pytest.mark.parametrize(
    "refs",
    [
        ("SharedSecret", "sharedsecret"),
        ("foo", "foo."),
        ("TIKHUB_API_KEY", "other"),
        ("LLM_API_KEY", "other"),
        ("FEISHU-CONNECTORS.JSON", "other"),
        ("Nested", "nested/child"),
        ("CON", "other"),
        ("nested/NUL.txt", "other"),
    ],
)
def test_windows_equivalent_or_reserved_refs_fail_before_writes(
    tmp_path: Path,
    refs: tuple[str, str],
) -> None:
    """非法目标在第一项写入前失败，既有 Provider 凭据保持原值。"""
    provider = tmp_path / "tikhub_api_key"
    provider.write_text("fixture-provider", encoding="utf-8")
    raw = json.dumps([connector(app_secret_ref=refs[0]), connector("b", app_secret_ref=refs[1])])
    with pytest.raises(FeishuConfigInputError):
        config = parse_feishu_config_input(raw)
        materialize_feishu_config(tmp_path, config)
    assert list(tmp_path.iterdir()) == [provider]
    assert provider.read_text() == "fixture-provider"


@pytest.mark.skipif(os.name != "posix", reason="Linux 保留原有大小写敏感引用")
def test_linux_case_sensitive_manual_refs_remain_distinct(tmp_path: Path) -> None:
    """Linux 合法的历史大小写引用不因 Windows 防护被更改。"""
    raw = json.dumps([connector(app_secret_ref="Shared"), connector("b", app_secret_ref="shared")])
    config = parse_feishu_config_input(raw)
    materialize_feishu_config(tmp_path, config)
    assert (tmp_path / "Shared").read_text().strip() == "fixture-a-credential"
    assert (tmp_path / "shared").read_text().strip() == "fixture-b-credential"


@pytest.mark.parametrize("location", ["root", "parent", "target"])
def test_symbolic_links_cannot_receive_credentials(tmp_path: Path, location: str) -> None:
    """批准目录、子目录及目标链接均不能把凭据带出写入边界。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    target = root / "nested" / "credential"
    link = {"root": root, "parent": root / "nested", "target": target}[location]
    if location == "root":
        root.rmdir()
    if location == "target":
        target.parent.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 权限不能创建符号链接；Linux 验证必须执行")
    config = parse_feishu_config_input(json.dumps([connector(app_secret_ref="nested/credential")]))
    with pytest.raises(FeishuConfigInputError):
        materialize_feishu_config(root, config)
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="真实 Linux UID/GID 与 Secret 读取验证")
def test_compose_bootstrap_cli_files_are_readable_by_business_uid(tmp_path: Path) -> None:
    """正式 bootstrap CLI 写入后，降至业务 UID 的新进程加载配置并读取各自凭据。"""
    if os.geteuid() != 0:
        pytest.skip("该启动准备入口需要 root；隔离 Linux 容器必须执行")
    root = tmp_path / "host"
    raw = json.dumps([connector(), connector("b", app_secret_ref="nested/b")], indent=2)
    environment = {**os.environ, "AIMA_FEISHU_CONNECTORS": raw}
    script = Path(__file__).resolve().parents[3] / "scripts/deploy/prepare_host.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--runtime-only"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "fixture" not in result.stdout + result.stderr
    secrets = root / "shared/provider-secrets"
    for name in ("feishu_a_secret", "nested/b", CONNECTORS_FILENAME):
        info = (secrets / name).stat()
        assert (info.st_uid, info.st_gid, info.st_mode & 0o777) == (10001, 10001, 0o600)
    # pytest 临时目录只放测试事实，允许业务 UID 穿过外层测试目录。
    parent = tmp_path
    while parent != Path("/tmp") and parent != parent.parent:
        parent.chmod(0o755)
        parent = parent.parent
    root.chmod(0o755)
    (root / "shared").chmod(0o755)
    code = (
        "import os; os.setgid(10001); os.setuid(10001); "
        "from aima_ugc.platform.config import load_settings; "
        "from aima_ugc.platform.security.secrets import read_secret_ref; "
        "from pathlib import Path; "
        f"root=Path({str(secrets)!r}); "
        f"s=load_settings({{'AIMA_FEISHU_CONNECTORS_FILE':str(root/{CONNECTORS_FILENAME!r})}}); "
        "assert len(s.feishu_connectors)==2; "
        "assert read_secret_ref(root,s.feishu_connectors.get('b').app_secret_ref)"
        ".get_secret_value()=='fixture-b-credential'"
    )
    reader = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert reader.returncode == 0, reader.stderr


@pytest.mark.skipif(os.name != "posix", reason="真实 Linux CLI expanduser 兼容验证")
def test_bootstrap_cli_expands_home_once_for_all_outputs(tmp_path: Path) -> None:
    """目录准备与飞书落盘使用相同展开根，cwd 不产生第二份凭据。"""
    if os.geteuid() != 0:
        pytest.skip("正式宿主准备要求 root")
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    script = Path(__file__).resolve().parents[3] / "scripts/deploy/prepare_host.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", "~/host", "--runtime-only"],
        cwd=cwd,
        env={**os.environ, "HOME": str(home), "AIMA_FEISHU_CONNECTORS": json.dumps([connector()])},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (home / "host/shared/provider-secrets/feishu_a_secret").is_file()
    assert (home / "host/shared/provider-secrets" / CONNECTORS_FILENAME).is_file()
    assert not (cwd / "~").exists()
