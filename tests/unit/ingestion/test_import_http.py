from __future__ import annotations

import pytest
from aima_ugc.bootstrap.import_http import _validate_upload_filename
from aima_ugc.modules.ingestion.http import InvalidImportFile


@pytest.mark.parametrize(
    "filename",
    (
        "../source.xlsx",
        "folder/source.xlsx",
        "folder\\source.xlsx",
        "C:source.xlsx",
        "source.xlsx\x00ignored",
        "source\x01.xlsx",
        "source.xls",
    ),
)
def test_upload_filename_is_host_os_independent(filename: str) -> None:
    with pytest.raises(InvalidImportFile):
        _validate_upload_filename(filename)


def test_unicode_xlsx_basename_is_accepted() -> None:
    assert _validate_upload_filename("爱玛舆情.xlsx") == "爱玛舆情.xlsx"
