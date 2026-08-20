"""Excel OOXML 上传的中央目录安全校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from struct import Struct
from struct import error as StructError
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

MAX_MULTIPART_BODY_BYTES = 550 * 1024 * 1024
MAX_XLSX_FILE_BYTES = 500 * 1024 * 1024
MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES = 5 * 1024**3
MAX_XLSX_MEMBER_BYTES = 4 * 1024**3
MAX_XLSX_ARCHIVE_MEMBERS = 2048
MAX_XLSX_COMPRESSION_RATIO = 100

_REQUIRED_OOXML_MEMBERS = frozenset({"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"})
_SUPPORTED_COMPRESSION = frozenset({ZIP_STORED, ZIP_DEFLATED})
_LOCAL_FILE_HEADER = Struct("<4s5H3L2H")


class InvalidXlsxError(ValueError):
    """文件不是结构安全且可识别的 OOXML 工作簿。"""


class XlsxResourceLimitError(ValueError):
    """文件或解压资源超过已批准上限。"""


@dataclass(frozen=True, slots=True)
class XlsxArchiveSummary:
    """不解压成员即可获得的工作簿资源摘要。"""

    member_count: int
    total_uncompressed_bytes: int


def validate_xlsx_archive(path: Path) -> XlsxArchiveSummary:
    """只读取 ZIP 中央目录，验证 OOXML 身份、路径和资源上限。"""

    source = Path(path)
    if source.suffix.casefold() != ".xlsx":
        raise InvalidXlsxError("只接受 .xlsx 文件")
    try:
        archive_bytes = source.stat().st_size
    except OSError as exc:
        raise InvalidXlsxError("无法读取 Excel 文件") from exc
    if archive_bytes > MAX_XLSX_FILE_BYTES:
        raise XlsxResourceLimitError("Excel 文件超过 500 MiB 上限")

    with source.open("rb") as source_file:
        return validate_xlsx_stream(
            source_file,
            filename=source.name,
            file_size=archive_bytes,
        )


def validate_xlsx_stream(
    source: BinaryIO,
    *,
    filename: str,
    file_size: int,
) -> XlsxArchiveSummary:
    """校验可 seek 上传流；调用完成后把游标恢复到开头。"""

    if Path(filename).suffix.casefold() != ".xlsx":
        raise InvalidXlsxError("只接受 .xlsx 文件")
    if file_size < 0:
        raise InvalidXlsxError("Excel 文件大小不合法")
    if file_size > MAX_XLSX_FILE_BYTES:
        raise XlsxResourceLimitError("Excel 文件超过 500 MiB 上限")
    try:
        source.seek(0)
        with ZipFile(source) as archive:
            entries = archive.infolist()
    except (BadZipFile, OSError) as exc:
        raise InvalidXlsxError("文件不是合法的 XLSX ZIP 结构") from exc

    if len(entries) > MAX_XLSX_ARCHIVE_MEMBERS:
        raise XlsxResourceLimitError("XLSX 成员数量超过 2048 个上限")

    names: set[str] = set()
    total_uncompressed = 0
    raw_names = tuple(_read_raw_member_name(source, entry) for entry in entries)

    for entry, raw_name in zip(entries, raw_names, strict=True):
        _validate_member_name(raw_name)
        _validate_member_name(entry.filename)
        if entry.filename in names:
            raise InvalidXlsxError("XLSX 包含重复成员名")
        names.add(entry.filename)
        if entry.flag_bits & 0x1:
            raise InvalidXlsxError("不接受加密的 XLSX 成员")
        if entry.compress_type not in _SUPPORTED_COMPRESSION:
            raise InvalidXlsxError("XLSX 使用了不支持的压缩算法")
        if entry.file_size > MAX_XLSX_MEMBER_BYTES:
            raise XlsxResourceLimitError("XLSX 单成员超过 4 GiB 上限")
        if entry.file_size and (
            entry.compress_size == 0
            or entry.file_size > entry.compress_size * MAX_XLSX_COMPRESSION_RATIO
        ):
            raise XlsxResourceLimitError("XLSX 单成员压缩比超过 100:1 上限")
        total_uncompressed += entry.file_size
        if total_uncompressed > MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES:
            raise XlsxResourceLimitError("XLSX 解压总量超过 5 GiB 上限")

    if total_uncompressed and (
        file_size == 0 or total_uncompressed > file_size * MAX_XLSX_COMPRESSION_RATIO
    ):
        raise XlsxResourceLimitError("XLSX 整体压缩比超过 100:1 上限")
    if not _REQUIRED_OOXML_MEMBERS.issubset(names):
        raise InvalidXlsxError("XLSX 缺少必要的 OOXML 成员")
    source.seek(0)
    return XlsxArchiveSummary(
        member_count=len(entries),
        total_uncompressed_bytes=total_uncompressed,
    )


def _validate_member_name(name: str) -> None:
    if (
        not name
        or "\\" in name
        or "//" in name
        or name.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise InvalidXlsxError("XLSX 包含不安全的成员名")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise InvalidXlsxError("XLSX 包含不安全的成员名")
    if path.parts and ":" in path.parts[0]:
        raise InvalidXlsxError("XLSX 包含不安全的成员名")


def _read_raw_member_name(source_file: BinaryIO, entry: ZipInfo) -> str:
    try:
        source_file.seek(entry.header_offset)
        header = source_file.read(_LOCAL_FILE_HEADER.size)
        fields = _LOCAL_FILE_HEADER.unpack(header)
        if fields[0] != b"PK\x03\x04":
            raise InvalidXlsxError("XLSX 成员本地文件头无效")
        flag_bits = fields[2]
        name_size = fields[-2]
        raw_name = source_file.read(name_size)
        encoding = "utf-8" if flag_bits & 0x800 else "cp437"
        return raw_name.decode(encoding)
    except (OSError, StructError, UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, InvalidXlsxError):
            raise
        raise InvalidXlsxError("XLSX 成员名无法解析") from exc


__all__ = [
    "MAX_MULTIPART_BODY_BYTES",
    "MAX_XLSX_ARCHIVE_MEMBERS",
    "MAX_XLSX_COMPRESSION_RATIO",
    "MAX_XLSX_FILE_BYTES",
    "MAX_XLSX_MEMBER_BYTES",
    "MAX_XLSX_TOTAL_UNCOMPRESSED_BYTES",
    "InvalidXlsxError",
    "XlsxArchiveSummary",
    "XlsxResourceLimitError",
    "validate_xlsx_archive",
    "validate_xlsx_stream",
]
