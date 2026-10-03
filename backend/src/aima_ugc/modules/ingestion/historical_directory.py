"""管理员批准只读根目录下的历史 XLSX 枚举。"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_REPARSE_POINT = 0x400
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500


class HistoricalDirectoryUnavailable(RuntimeError):
    pass


class InvalidHistoricalRelativePath(ValueError):
    pass


class InvalidHistoricalDirectoryCursor(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HistoricalDirectoryEntry:
    relative_path: str
    name: str
    kind: str
    byte_size: int | None
    modified_at_ns: int


@dataclass(frozen=True, slots=True)
class HistoricalDirectoryPage:
    items: tuple[HistoricalDirectoryEntry, ...]
    next_cursor: str | None
    has_more: bool


class HistoricalDirectoryBrowser:
    """只枚举批准根内的直接子目录和 XLSX，不提供文件管理能力。"""

    def __init__(self, root: Path | None, *, managed_wisersone_root: Path | None = None) -> None:
        self._configured_root = root
        self._managed_wisersone_root = managed_wisersone_root

    def _is_managed(self, relative_path: str) -> bool:
        parts = _relative_parts(relative_path)
        # 既有批准根内同名目录优先，不能静默遮蔽用户已有文件。
        return bool(
            self._managed_wisersone_root is not None
            and parts
            and parts[0] == "wisersone"
            and not (self._root() / "wisersone").exists()
        )

    def _path_root(self, relative_path: str) -> Path:
        return self._root(managed=self._is_managed(relative_path))

    def list_entries(
        self,
        *,
        relative_path: str,
        cursor: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> HistoricalDirectoryPage:
        if limit < 1 or limit > _MAX_LIMIT:
            raise ValueError(f"limit 必须在 1 到 {_MAX_LIMIT} 之间")
        root = self._path_root(relative_path)
        directory = self.resolve(relative_path, require_directory=True)
        candidates = self._iter_entries(root, directory)
        if not _relative_parts(relative_path) and self._managed_wisersone_root is not None:
            managed = self._managed_wisersone_root
            if managed.is_dir() and not (root / "wisersone").exists():
                candidates.append(
                    HistoricalDirectoryEntry(
                        "wisersone", "wisersone", "directory", None, managed.stat().st_mtime_ns
                    )
                )
        entries = sorted(
            candidates,
            key=lambda item: (
                0 if item.kind == "directory" else 1,
                item.name.casefold(),
                item.name,
            ),
        )
        offset = _decode_cursor(cursor, relative_path=relative_path) if cursor else 0
        if offset < 0 or offset > len(entries):
            raise InvalidHistoricalDirectoryCursor("目录游标超出当前结果范围")
        page = entries[offset : offset + limit]
        next_offset = offset + len(page)
        has_more = next_offset < len(entries)
        return HistoricalDirectoryPage(
            items=tuple(page),
            next_cursor=(
                _encode_cursor(relative_path=relative_path, offset=next_offset)
                if has_more
                else None
            ),
            has_more=has_more,
        )

    def resolve(self, relative_path: str, *, require_directory: bool = False) -> Path:
        """解析一个 POSIX 相对路径，并拒绝每一级链接/Junction/逃逸。"""

        root = self._path_root(relative_path)
        parts = _relative_parts(relative_path)
        if self._managed_wisersone_root is not None and parts[:2] == ("wisersone", ".staging"):
            raise InvalidHistoricalRelativePath("WisersOne 暂存文件尚未发布，不能导入。")
        if self._is_managed(relative_path):
            parts = parts[1:]
        current = root
        for part in parts:
            current = current / part
            try:
                stat = current.stat(follow_symlinks=False)
            except OSError as exc:
                raise InvalidHistoricalRelativePath("相对路径不存在或不可访问") from exc
            if current.is_symlink() or bool(
                getattr(stat, "st_file_attributes", 0) & _REPARSE_POINT
            ):
                raise InvalidHistoricalRelativePath("历史目录路径不能包含链接或 Junction")
            resolved = current.resolve(strict=True)
            if not _inside(root, resolved):
                raise InvalidHistoricalRelativePath("历史目录路径逃逸批准根目录")
            current = resolved
        if require_directory and not current.is_dir():
            raise InvalidHistoricalRelativePath("请求路径不是目录")
        return current

    def discover_xlsx(
        self,
        *,
        relative_paths: tuple[str, ...],
        recursive: bool,
        max_files: int,
        max_depth: int,
    ) -> tuple[HistoricalDirectoryEntry, ...]:
        """有界发现显式选择的文件/目录，返回稳定的相对路径 Manifest。"""

        if not relative_paths:
            raise InvalidHistoricalRelativePath("至少选择一个目录或 XLSX 文件")
        if max_files < 1 or max_depth < 1:
            raise ValueError("扫描文件数和目录深度上限必须为正数")
        discovered: dict[str, HistoricalDirectoryEntry] = {}
        pending: list[tuple[str, int]] = []
        for relative_path in relative_paths:
            root = self._path_root(relative_path)
            resolved = self.resolve(relative_path)
            if resolved.is_file():
                if resolved.suffix.casefold() != ".xlsx":
                    raise InvalidHistoricalRelativePath("历史迁移只接受 XLSX 文件")
                entry = self._entry(root, resolved)
                discovered[entry.relative_path] = entry
                if len(discovered) > max_files:
                    raise InvalidHistoricalRelativePath("历史目录文件数超过配置上限")
            elif resolved.is_dir():
                pending.append((self._entry(root, resolved).relative_path, 0))
            else:
                raise InvalidHistoricalRelativePath("选择路径不是目录或 XLSX 文件")

        while pending:
            relative_directory, depth = pending.pop(0)
            page = self.list_entries(relative_path=relative_directory, limit=_MAX_LIMIT)
            entries = list(page.items)
            cursor = page.next_cursor
            while cursor is not None:
                page = self.list_entries(
                    relative_path=relative_directory,
                    cursor=cursor,
                    limit=_MAX_LIMIT,
                )
                entries.extend(page.items)
                cursor = page.next_cursor
            for entry in entries:
                if entry.kind == "file":
                    discovered.setdefault(entry.relative_path, entry)
                    if len(discovered) > max_files:
                        raise InvalidHistoricalRelativePath("历史目录文件数超过配置上限")
                elif recursive:
                    child_depth = depth + 1
                    if child_depth > max_depth:
                        raise InvalidHistoricalRelativePath("历史目录深度超过配置上限")
                    pending.append((entry.relative_path, child_depth))
        return tuple(sorted(discovered.values(), key=lambda item: item.relative_path.casefold()))

    def describe(self, relative_path: str) -> HistoricalDirectoryEntry:
        """读取同一批准视图的 Manifest 身份，受管 alias 不暴露宿主绝对路径。"""
        return self._entry(self._path_root(relative_path), self.resolve(relative_path))

    def selects_managed_file(
        self, file_relative_path: str, *, relative_paths: tuple[str, ...], recursive: bool
    ) -> bool:
        """按同一批准视图判断冻结选择是否消费受管文件，无需文件仍然存在。"""
        if self._managed_wisersone_root is None:
            return False
        target = _relative_parts(file_relative_path)
        if not target or target[0] != "wisersone":
            return False
        # 同名用户目录仍优先；不能因文本路径相同而保护另一个物理文件。
        path_root = self._path_root(file_relative_path)
        visible = path_root.joinpath(
            *(target[1:] if self._is_managed(file_relative_path) else target)
        )
        managed = self._managed_wisersone_root.joinpath(*target[1:])
        if visible.resolve() != managed.resolve():
            return False
        for selected in relative_paths:
            parts = _relative_parts(selected)
            if parts == target or parts == target[:-1]:
                return True
            if recursive and target[: len(parts)] == parts:
                return True
        return False

    def _root(self, *, managed: bool = False) -> Path:
        root = self._managed_wisersone_root if managed else self._configured_root
        if root is None:
            raise HistoricalDirectoryUnavailable("未配置历史导入根目录")
        try:
            stat = root.stat(follow_symlinks=False)
            if root.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & _REPARSE_POINT):
                raise HistoricalDirectoryUnavailable("历史导入根目录不能是链接或 Junction")
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise HistoricalDirectoryUnavailable("历史导入根目录不存在或不可访问") from exc
        if not resolved.is_dir():
            raise HistoricalDirectoryUnavailable("历史导入根配置不是目录")
        return resolved

    def _iter_entries(self, root: Path, directory: Path) -> list[HistoricalDirectoryEntry]:
        result: list[HistoricalDirectoryEntry] = []
        try:
            children = tuple(directory.iterdir())
        except OSError as exc:
            raise HistoricalDirectoryUnavailable("历史目录不可枚举") from exc
        for child in children:
            try:
                stat = child.stat(follow_symlinks=False)
            except OSError:
                continue
            if child.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & _REPARSE_POINT):
                continue
            resolved = child.resolve(strict=True)
            if not _inside(root, resolved):
                continue
            if resolved.is_dir():
                kind = "directory"
                byte_size = None
            elif resolved.is_file() and resolved.suffix.casefold() == ".xlsx":
                kind = "file"
                byte_size = stat.st_size
            else:
                continue
            entry = self._entry(root, resolved, kind=kind, stat=stat, byte_size=byte_size)
            if self._managed_wisersone_root is not None and _relative_parts(entry.relative_path)[
                :2
            ] == ("wisersone", ".staging"):
                continue
            result.append(entry)
        return result

    def _entry(
        self,
        root: Path,
        path: Path,
        *,
        kind: str | None = None,
        stat: os.stat_result | None = None,
        byte_size: int | None = None,
    ) -> HistoricalDirectoryEntry:
        resolved_stat = path.stat(follow_symlinks=False) if stat is None else stat
        resolved_kind = kind or ("directory" if path.is_dir() else "file")
        resolved_size = (
            byte_size
            if byte_size is not None
            else (resolved_stat.st_size if path.is_file() else None)
        )
        return HistoricalDirectoryEntry(
            relative_path=(
                "wisersone/" + path.relative_to(root).as_posix()
                if self._managed_wisersone_root is not None
                and root == self._managed_wisersone_root.resolve()
                and root != self._configured_root
                else path.relative_to(root).as_posix()
            ),
            name=path.name,
            kind=resolved_kind,
            byte_size=resolved_size,
            modified_at_ns=resolved_stat.st_mtime_ns,
        )


def _relative_parts(value: str) -> tuple[str, ...]:
    if "\x00" in value or "\\" in value:
        raise InvalidHistoricalRelativePath("历史路径必须是无歧义的 POSIX 相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("//") or ":" in value:
        raise InvalidHistoricalRelativePath("历史路径必须位于批准根目录内")
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if any(part == ".." for part in parts):
        raise InvalidHistoricalRelativePath("历史路径不能包含上级目录")
    # Windows 的文件系统接受大小写等价路径；保护判断与读取必须采用同一等价规则。
    # Linux 的 normcase 保持原值，因此不会把两个不同文件或目录合并。
    return tuple(os.path.normcase(part) for part in parts)


def _inside(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        return False


def _encode_cursor(*, relative_path: str, offset: int) -> str:
    payload = json.dumps({"path": relative_path, "offset": offset}, separators=(",", ":")).encode(
        "utf-8"
    )
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(value: str, *, relative_path: str) -> int:
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        if not isinstance(payload, dict) or payload.get("path") != relative_path:
            raise ValueError
        offset = payload["offset"]
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise InvalidHistoricalDirectoryCursor("历史目录游标无效") from exc
    return offset


__all__ = [
    "HistoricalDirectoryBrowser",
    "HistoricalDirectoryEntry",
    "HistoricalDirectoryPage",
    "HistoricalDirectoryUnavailable",
    "InvalidHistoricalDirectoryCursor",
    "InvalidHistoricalRelativePath",
]
