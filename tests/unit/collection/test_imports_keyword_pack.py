from __future__ import annotations

from pathlib import Path

import pytest

from aima_ugc.adapters.providers.imports_test import test as imports_test


def test_imports_test_uses_separate_keyword_pack_file() -> None:
    assert hasattr(imports_test, "KEYWORD_PACK_FILE")
    assert not hasattr(imports_test, "KEYWORDS")
    path = imports_test.KEYWORD_PACK_FILE
    assert isinstance(path, Path)
    assert path.name == "keyword_pack.txt"
    assert path.is_file()


def test_keyword_pack_loader_keeps_102_source_model_rows_and_brand_keyword() -> None:
    from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack

    pack = load_keyword_pack(imports_test.KEYWORD_PACK_FILE)

    assert pack.source_keyword_count == 103
    assert pack.effective_keyword_count == 96
    assert pack.keywords[0] == "爱玛"
    assert "元宇宙Pony" in pack.keywords
    assert "凌志26-M" in pack.keywords
    assert "黑翼S3 60" in pack.keywords
    assert "黑翼S360" not in pack.keywords


def test_keyword_pack_loader_ignores_blank_lines_and_comments_and_fails_if_empty(
    tmp_path: Path,
) -> None:
    from aima_ugc.adapters.providers.imports_test.keyword_pack import load_keyword_pack

    populated = tmp_path / "keywords.txt"
    populated.write_text("# 注释\n\n爱玛\n  F30  \n", encoding="utf-8")
    pack = load_keyword_pack(populated)
    assert pack.keywords == ("爱玛", "F30")

    empty = tmp_path / "empty.txt"
    empty.write_text("# 只有注释\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="至少需要一个"):
        load_keyword_pack(empty)
