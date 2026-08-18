from __future__ import annotations

from pathlib import Path

import pytest
from aima_ugc.platform.security import (
    SecretFileError,
    read_secret_file,
    validate_secret_ref,
)


def test_validate_secret_ref_rejects_path_escape() -> None:
    assert validate_secret_ref("providers/tikhub/main") == "providers/tikhub/main"
    for invalid in ("../secret", "/absolute", "providers\\secret", "a//b", "a/./b"):
        with pytest.raises(ValueError):
            validate_secret_ref(invalid)


def test_read_secret_file_trims_only_trailing_newline(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    secret_file = secret_dir / "provider-key"
    secret_file.write_text("  keep-spaces  \r\n", encoding="utf-8")

    value = read_secret_file(secret_file, root=secret_dir)

    assert value.get_secret_value() == "  keep-spaces  "


def test_read_secret_file_rejects_symlink_even_when_target_is_regular_file(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("must-not-read", encoding="utf-8")
    link = secret_dir / "provider-key"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("当前测试文件系统不允许创建 symlink")

    with pytest.raises(SecretFileError, match="符号链接|根目录"):
        read_secret_file(link, root=secret_dir)


def test_read_secret_file_rejects_explicit_root_escape(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("must-not-read", encoding="utf-8")

    with pytest.raises(SecretFileError, match="根目录"):
        read_secret_file(outside, root=secret_dir)
