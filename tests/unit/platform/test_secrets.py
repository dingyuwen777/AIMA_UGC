import pytest

from aima_ugc.platform.security import SecretFileError, read_secret_file


def test_secret_reader_only_removes_trailing_newlines(tmp_path) -> None:
    secret_file = tmp_path / "postgres_password"
    secret_file.write_text("  meaningful spaces  \r\n", encoding="utf-8")

    secret = read_secret_file(secret_file)

    assert secret.get_secret_value() == "  meaningful spaces  "


def test_secret_reader_rejects_nul_without_leaking_secret(tmp_path) -> None:
    secret_file = tmp_path / "postgres_password"
    secret_file.write_bytes(b"actual-secret-value\x00hidden")

    with pytest.raises(SecretFileError) as exc_info:
        read_secret_file(secret_file)

    assert "actual-secret-value" not in str(exc_info.value)


def test_secret_reader_rejects_oversized_file(tmp_path) -> None:
    secret_file = tmp_path / "postgres_password"
    secret_file.write_text("x" * 32, encoding="utf-8")

    with pytest.raises(SecretFileError):
        read_secret_file(secret_file, max_bytes=16)
