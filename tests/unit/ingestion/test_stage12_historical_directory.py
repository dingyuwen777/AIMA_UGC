"""Stage 12B 服务器历史目录的 fail-closed 路径安全。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from aima_ugc.modules.ingestion.historical_directory import (
    HistoricalDirectoryBrowser,
    HistoricalDirectoryUnavailable,
    InvalidHistoricalDirectoryCursor,
    InvalidHistoricalRelativePath,
)


def test_directory_browser_only_returns_relative_direct_children_and_xlsx(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    (root / "batch-b").mkdir(parents=True)
    (root / "batch-a").mkdir()
    (root / "b.xlsx").write_bytes(b"xlsx-b")
    (root / "a.XLSX").write_bytes(b"xlsx-a")
    (root / "ignored.csv").write_text("x", encoding="utf-8")

    page = HistoricalDirectoryBrowser(root).list_entries(relative_path="", limit=3)

    assert [item.relative_path for item in page.items] == ["batch-a", "batch-b", "a.XLSX"]
    assert page.has_more is True
    assert page.next_cursor is not None
    next_page = HistoricalDirectoryBrowser(root).list_entries(
        relative_path="",
        limit=3,
        cursor=page.next_cursor,
    )
    assert [item.relative_path for item in next_page.items] == ["b.xlsx"]
    assert all(
        not Path(item.relative_path).is_absolute() for item in (*page.items, *next_page.items)
    )


@pytest.mark.parametrize(
    "relative_path",
    (
        "../escape",
        "a/../../escape",
        "/absolute",
        r"C:\absolute",
        r"\\server\share",
        r"\\?\C:\device",
        "bad\x00path",
        "mixed\\separator",
    ),
)
def test_directory_browser_rejects_non_relative_or_ambiguous_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    with pytest.raises(InvalidHistoricalRelativePath):
        HistoricalDirectoryBrowser(root).list_entries(relative_path=relative_path)


def test_directory_browser_rejects_link_components(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 账户不允许创建测试符号链接")

    with pytest.raises(InvalidHistoricalRelativePath):
        HistoricalDirectoryBrowser(root).list_entries(relative_path="linked")


def test_directory_browser_is_unavailable_without_a_real_directory(tmp_path: Path) -> None:
    with pytest.raises(HistoricalDirectoryUnavailable):
        HistoricalDirectoryBrowser(None).list_entries(relative_path="")
    with pytest.raises(HistoricalDirectoryUnavailable):
        HistoricalDirectoryBrowser(tmp_path / "missing").list_entries(relative_path="")


@pytest.mark.parametrize("cursor", ("a", "WzFd"))
def test_directory_browser_rejects_malformed_cursor_without_internal_error(
    tmp_path: Path,
    cursor: str,
) -> None:
    root = tmp_path / "approved"
    root.mkdir()

    with pytest.raises(InvalidHistoricalDirectoryCursor):
        HistoricalDirectoryBrowser(root).list_entries(relative_path="", cursor=cursor)


def test_discovery_is_recursive_only_when_requested_and_deduplicates_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "approved"
    nested = root / "batch" / "nested"
    nested.mkdir(parents=True)
    direct = root / "batch" / "direct.xlsx"
    child = nested / "child.xlsx"
    direct.write_bytes(b"direct")
    child.write_bytes(b"child")

    browser = HistoricalDirectoryBrowser(root)

    non_recursive = browser.discover_xlsx(
        relative_paths=("batch", "batch/direct.xlsx"),
        recursive=False,
        max_files=10,
        max_depth=2,
    )
    recursive = browser.discover_xlsx(
        relative_paths=("batch",),
        recursive=True,
        max_files=10,
        max_depth=2,
    )

    assert [item.relative_path for item in non_recursive] == ["batch/direct.xlsx"]
    assert [item.relative_path for item in recursive] == [
        "batch/direct.xlsx",
        "batch/nested/child.xlsx",
    ]


def test_discovery_enforces_file_and_depth_limits_for_all_selection_shapes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "approved"
    nested = root / "a" / "b" / "c"
    nested.mkdir(parents=True)
    first = root / "first.xlsx"
    second = root / "second.xlsx"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    (nested / "deep.xlsx").write_bytes(b"deep")
    browser = HistoricalDirectoryBrowser(root)

    with pytest.raises(InvalidHistoricalRelativePath, match="文件数"):
        browser.discover_xlsx(
            relative_paths=("first.xlsx", "second.xlsx"),
            recursive=False,
            max_files=1,
            max_depth=2,
        )
    with pytest.raises(InvalidHistoricalRelativePath, match="深度"):
        browser.discover_xlsx(
            relative_paths=("a",),
            recursive=True,
            max_files=10,
            max_depth=1,
        )
