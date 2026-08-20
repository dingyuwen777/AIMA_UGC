from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from aima_ugc.modules.ingestion.xlsx_security import (
    MAX_MULTIPART_BODY_BYTES,
    MAX_XLSX_ARCHIVE_MEMBERS,
    MAX_XLSX_FILE_BYTES,
    MAX_XLSX_MEMBER_BYTES,
    MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES,
    InvalidXlsxError,
    XlsxResourceLimitError,
    validate_xlsx_archive,
    validate_xlsx_stream,
)


def _write_minimal_xlsx(path: Path, *, extra: tuple[tuple[str, bytes], ...] = ()) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
        for name, payload in extra:
            archive.writestr(name, payload)
    for name, _ in extra:
        if "\\" in name:
            normalized = name.replace("\\", "/").encode()
            path.write_bytes(path.read_bytes().replace(normalized, name.encode()))


def test_stage8b_upload_limits_are_exact_binary_sizes() -> None:
    assert MAX_MULTIPART_BODY_BYTES == 550 * 1024 * 1024
    assert MAX_XLSX_FILE_BYTES == 500 * 1024 * 1024
    assert MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES == 5 * 1024**3
    assert MAX_XLSX_MEMBER_BYTES == 4 * 1024**3
    assert MAX_XLSX_ARCHIVE_MEMBERS == 2048


def test_valid_xlsx_central_directory_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "valid.xlsx"
    _write_minimal_xlsx(path)

    summary = validate_xlsx_archive(path)

    assert summary.member_count == 3
    assert summary.total_uncompressed_bytes > 0


@pytest.mark.parametrize(
    "member_name",
    ("../escape.xml", "/absolute.xml", "xl\\bad.xml", "xl//bad.xml", "xl/\x01bad.xml"),
)
def test_unsafe_xlsx_member_name_is_rejected(tmp_path: Path, member_name: str) -> None:
    path = tmp_path / "unsafe.xlsx"
    _write_minimal_xlsx(path, extra=((member_name, b"bad"),))

    with pytest.raises(InvalidXlsxError, match="成员名"):
        validate_xlsx_archive(path)


def test_duplicate_xlsx_member_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.xlsx"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
        archive.writestr("xl/workbook.xml", b"<other/>")

    with pytest.raises(InvalidXlsxError, match="重复"):
        validate_xlsx_archive(path)


def test_resource_limits_are_checked_without_extracting_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "large.xlsx"
    _write_minimal_xlsx(path)
    original = ZipFile.infolist

    def oversized(archive: ZipFile) -> list[ZipInfo]:
        entries = original(archive)
        entries[0].file_size = MAX_XLSX_MEMBER_BYTES + 1
        return entries

    monkeypatch.setattr(ZipFile, "infolist", oversized)

    with pytest.raises(XlsxResourceLimitError, match="单成员"):
        validate_xlsx_archive(path)


def test_file_size_limit_is_checked_before_zip_parsing() -> None:
    with pytest.raises(XlsxResourceLimitError, match="500 MiB"):
        validate_xlsx_stream(
            BytesIO(b"not-a-zip"),
            filename="large.xlsx",
            file_size=MAX_XLSX_FILE_BYTES + 1,
        )


def test_member_count_limit_is_checked_before_member_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "members.xlsx"
    _write_minimal_xlsx(path)
    original = ZipFile.infolist

    def too_many(archive: ZipFile) -> list[ZipInfo]:
        entries = original(archive)
        return [entries[0]] * (MAX_XLSX_ARCHIVE_MEMBERS + 1)

    monkeypatch.setattr(ZipFile, "infolist", too_many)
    with pytest.raises(XlsxResourceLimitError, match="成员数量"):
        validate_xlsx_archive(path)


def test_total_uncompressed_and_ratio_limits_are_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "total.xlsx"
    _write_minimal_xlsx(path)
    original = ZipFile.infolist

    def oversized_total(archive: ZipFile) -> list[ZipInfo]:
        entries = original(archive)
        for entry in entries[:2]:
            entry.file_size = 3 * 1024**3
            entry.compress_size = 32 * 1024**2
        return entries

    monkeypatch.setattr(ZipFile, "infolist", oversized_total)
    with pytest.raises(XlsxResourceLimitError, match="解压总量"):
        validate_xlsx_archive(path)

    def excessive_ratio(archive: ZipFile) -> list[ZipInfo]:
        entries = original(archive)
        entries[0].file_size = 101
        entries[0].compress_size = 1
        return entries

    monkeypatch.setattr(ZipFile, "infolist", excessive_ratio)
    with pytest.raises(XlsxResourceLimitError, match="单成员压缩比"):
        validate_xlsx_archive(path)


@pytest.mark.parametrize("unsafe_kind", ("encrypted", "compression"))
def test_encrypted_or_unsupported_compression_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_kind: str,
) -> None:
    path = tmp_path / "unsafe-compression.xlsx"
    _write_minimal_xlsx(path)
    original = ZipFile.infolist

    def unsafe(archive: ZipFile) -> list[ZipInfo]:
        entries = original(archive)
        if unsafe_kind == "encrypted":
            entries[0].flag_bits |= 0x1
        else:
            entries[0].compress_type = 99
        return entries

    monkeypatch.setattr(ZipFile, "infolist", unsafe)
    with pytest.raises(InvalidXlsxError):
        validate_xlsx_archive(path)


def test_required_ooxml_members_are_mandatory(tmp_path: Path) -> None:
    path = tmp_path / "missing-workbook.xlsx"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")

    with pytest.raises(InvalidXlsxError, match="必要"):
        validate_xlsx_archive(path)
