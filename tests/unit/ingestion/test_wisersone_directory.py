"""受管来源视图必须保护暂存文件，同时保持旧目录合法行为。"""

from pathlib import Path

import pytest
from aima_ugc.modules.ingestion.historical_directory import (
    HistoricalDirectoryBrowser,
    InvalidHistoricalRelativePath,
)


def test_managed_view_lists_published_files_but_rejects_staging(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    managed = tmp_path / "managed"
    approved.mkdir()
    (managed / ".staging" / "pending").mkdir(parents=True)
    (managed / ".staging" / "pending" / "partial.xlsx").write_bytes(b"partial")
    (managed / "published").mkdir()
    published = managed / "published" / "ready.xlsx"
    published.write_bytes(b"published")
    browser = HistoricalDirectoryBrowser(approved, managed_wisersone_root=managed)
    assert [e.relative_path for e in browser.list_entries(relative_path="").items] == ["wisersone"]
    assert [
        e.relative_path
        for e in browser.discover_xlsx(
            relative_paths=("wisersone",), recursive=True, max_files=10, max_depth=3
        )
    ] == ["wisersone/published/ready.xlsx"]
    assert browser.resolve("wisersone/published/ready.xlsx") == published
    with pytest.raises(InvalidHistoricalRelativePath):
        browser.resolve("wisersone/.staging/pending/partial.xlsx")
    with pytest.raises(InvalidHistoricalRelativePath):
        browser.resolve("wisersone/../approved/escape.xlsx")


def test_existing_directory_is_not_shadowed_by_managed_alias(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    managed = tmp_path / "managed"
    (approved / "wisersone").mkdir(parents=True)
    managed.mkdir()
    original = approved / "wisersone" / "old.xlsx"
    original.write_bytes(b"original")
    browser = HistoricalDirectoryBrowser(approved, managed_wisersone_root=managed)
    assert browser.resolve("wisersone/old.xlsx") == original
    assert len(browser.list_entries(relative_path="").items) == 1
