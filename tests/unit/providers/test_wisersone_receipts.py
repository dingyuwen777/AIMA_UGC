"""宿主提交回执保留网站任务身份，恢复不能再次点击导出。"""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.wisersone.export import WisersOneExporter
from aima_ugc.adapters.providers.wisersone.models import ExportTask, SubmissionUnknown


def test_saved_receipt_survives_exporter_restart_without_opening_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = uuid4()
    receipt = tmp_path / f"export-{run_id.hex}.json"
    receipt.write_text(
        json.dumps(
            {"schema_version": "wisersone-export-receipt.v1", "task_id": "website-existing"}
        ),
        encoding="utf-8",
    )

    def unexpected_browser(*args, **kwargs):
        raise AssertionError("已有完整回执时不能打开浏览器或发送新导出")

    def unexpected_callback(*args, **kwargs):
        raise AssertionError("读取已确认回执不能产生新提交意图")

    monkeypatch.setattr(WisersOneExporter, "_session", unexpected_browser)
    exporter = WisersOneExporter(auth_dir=tmp_path)
    assert exporter.saved_task(run_id) == ExportTask("website-existing")
    restarted = WisersOneExporter(auth_dir=tmp_path)
    assert restarted.submit(run_id, before_submit=unexpected_callback) == ExportTask(
        "website-existing"
    )
    assert receipt.is_file()


def test_missing_receipt_does_not_invent_a_confirmed_website_task(tmp_path: Path) -> None:
    assert WisersOneExporter(auth_dir=tmp_path).saved_task(uuid4()) is None


@pytest.mark.parametrize(
    "raw",
    [
        "broken JSON",
        '{"schema_version": "unknown", "task_id": "website-existing"}',
        '{"schema_version": "wisersone-export-receipt.v1", "task_id": ""}',
        '{"schema_version": "wisersone-export-receipt.v1", "task_id": 123}',
    ],
)
def test_corrupt_or_unsupported_receipt_requires_operator_check(tmp_path: Path, raw: str) -> None:
    run_id = uuid4()
    path = tmp_path / f"export-{run_id.hex}.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(SubmissionUnknown, match="提交回执损坏"):
        WisersOneExporter(auth_dir=tmp_path).saved_task(run_id)
    assert path.read_text(encoding="utf-8") == raw
