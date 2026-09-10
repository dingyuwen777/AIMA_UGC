from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from aima_ugc.adapters.feishu import FeishuConfigError, FeishuSyncError
from aima_ugc.entrypoints import representative_selection_main as entrypoint


def _selected_payload(*, eligible: bool = True) -> dict[str, object]:
    return {
        "content": {
            "row_number": 2,
            "platform": "抖音",
            "content_id": "content-1",
            "title": "真实使用体验",
            "text": "用户描述了具体通勤体验",
            "author": "普通用户",
            "published_at": "2026-09-01 10:00:00",
            "content_url": "https://example.test/content-1",
            "voice_type": "真实用户发声",
            "sentiment_label": "正面",
        },
        "decision": {
            "item_no": 1,
            "eligible": eligible,
            "sentiment": "正面" if eligible else None,
            "theme": "通勤体验",
            "reason": "包含具体使用事实",
            "score": 5,
            "exclusion_reason": None if eligible else "不符合入选条件",
        },
    }


def test_input_xlsx_option_can_be_repeated_for_multiple_labeled_workbooks() -> None:
    arguments = entrypoint.build_argument_parser().parse_args(
        [
            "--input-xlsx",
            "first.xlsx",
            "--input-xlsx",
            "second.xlsx",
            "--dry-run",
        ]
    )

    assert arguments.input_xlsx == [Path("first.xlsx"), Path("second.xlsx")]


def test_write_feishu_from_run_reads_existing_results_without_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "representative-run"
    run_dir.mkdir()
    results_path = run_dir / "selected_results.jsonl"
    results_path.write_text(
        json.dumps(_selected_payload(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    observed: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("只同步已有结果模式不应初始化 LLM")

    def fake_sync(*, settings: object, selected: object, output_dir: Path) -> object:
        del settings
        observed.extend([selected, output_dir])
        return SimpleNamespace(
            verification_errors=(),
            as_dict=lambda: {"created_count": 1, "updated_count": 0},
        )

    monkeypatch.setattr(entrypoint, "load_settings", lambda **kwargs: object())
    monkeypatch.setattr(entrypoint, "_create_llm", fail_if_called)
    monkeypatch.setattr(entrypoint, "_sync_to_feishu", fake_sync)

    assert entrypoint.main(["--write-feishu-from-run", str(run_dir)]) == 0
    selected = observed[0]
    assert isinstance(selected, tuple)
    assert selected[0].candidate.content.content_id == "content-1"
    assert observed[1] == run_dir.resolve()


def test_existing_selected_results_must_be_eligible(tmp_path: Path) -> None:
    run_dir = tmp_path / "representative-run"
    run_dir.mkdir()
    (run_dir / "selected_results.jsonl").write_text(
        json.dumps(_selected_payload(eligible=False), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(entrypoint.SelectedResultsFileError, match="可同步"):
        entrypoint._read_selected_results(run_dir, max_per_group=10)


def test_feishu_config_failure_summary_is_safe() -> None:
    error = FeishuConfigError(("AIMA_FEISHU_WIKI_TOKEN", "AIMA_FEISHU_TABLE_ID"))

    assert entrypoint._safe_error_code(error) == "feishu_config_incomplete"
    assert entrypoint._safe_error_message(error) == (
        "feishu_config_incomplete（缺少: AIMA_FEISHU_WIKI_TOKEN, AIMA_FEISHU_TABLE_ID）"
    )
    assert entrypoint._sync_failure_payload(error) == {
        "status": "failed",
        "error_code": "feishu_config_incomplete",
        "missing": ["AIMA_FEISHU_WIKI_TOKEN", "AIMA_FEISHU_TABLE_ID"],
    }


def test_feishu_sync_failure_summary_keeps_internal_detail_only() -> None:
    error = FeishuSyncError("飞书缺少 Upsert 必需字段: 平台")

    assert entrypoint._safe_error_code(error) == "feishu_sync_error"
    assert entrypoint._safe_error_message(error) == (
        "feishu_sync_error（飞书缺少 Upsert 必需字段: 平台）"
    )
    assert entrypoint._sync_failure_payload(error) == {
        "status": "failed",
        "error_code": "feishu_sync_error",
        "detail": "飞书缺少 Upsert 必需字段: 平台",
    }


def test_entrypoint_settings_load_explicit_env_file_without_mutating_process_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIMA_FEISHU_APP_ID=cli-from-file\n"
        "AIMA_FEISHU_APP_TOKEN=app-from-file\n"
        "AIMA_FEISHU_TABLE_ID=tbl-from-file\n"
        "AIMA_EXTERNAL_SECRET_DIR=.runtime/secrets\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("AIMA_FEISHU_APP_ID", raising=False)

    settings, environment = entrypoint._load_entrypoint_settings(env_file)

    assert settings.feishu_app_id == "cli-from-file"
    assert settings.feishu_app_token == "app-from-file"
    assert settings.feishu_table_id == "tbl-from-file"
    assert environment["AIMA_FEISHU_APP_ID"] == "cli-from-file"
