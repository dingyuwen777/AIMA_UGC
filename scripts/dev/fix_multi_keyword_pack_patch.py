from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:80]!r}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


# Stage 8E API fake/fixtures 跟随新 Contract。
path = "tests/api/test_stage8e_collection_runs.py"
replace_once(path, "from uuid import UUID\n", "from uuid import UUID\n")
replace_once(
    path,
    'BATCH_ID = UUID("44444444-4444-4444-8444-444444444444")\n',
    'BATCH_ID = UUID("44444444-4444-4444-8444-444444444444")\nPACK_ID = UUID("55555555-5555-4555-8555-555555555555")\n',
)
replace_once(
    path,
    '        assert request.keywords == ("爱玛", "爱玛 Q7")\n',
    '        assert request.keyword_pack_ids == (PACK_ID,)\n',
)
replace_once(
    path,
    '            "keyword_pack_ids": [str(uuid4())],\n',
    '            "keyword_pack_ids": [str(PACK_ID)],\n',
)
replace_once(
    path,
    '            "mode": "batch_supplement",\n            "keyword_pack_ids": [str(uuid4())],\n',
    '            "mode": "batch_supplement",\n            "keyword_pack_ids": [str(PACK_ID)],\n            "import_batch_id": str(BATCH_ID),\n',
)

# Stage 8B PostgreSQL integration：上传显式携带所选词包；断言新冻结快照。
path = "tests/integration/ingestion/test_stage8b_import_http_worker.py"
replace_once(
    path,
    '''        files={\n            "file": (\n                "stage8b.xlsx",\n                _xlsx(),\n                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",\n            )\n        },''',
    '''        files=[\n            (\n                "file",\n                (\n                    "stage8b.xlsx",\n                    _xlsx(),\n                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",\n                ),\n            ),\n            ("keyword_pack_ids", (None, pack_id)),\n        ],''',
)
replace_once(
    path,
    '''        assert persisted_batch["stats"]["relevance"]["effective_keywords"] == ["爱玛"]\n        assert persisted_job["payload"]["relevance"] == persisted_batch["stats"]["relevance"]''',
    '''        selection = persisted_batch["stats"]["keyword_selection"]\n        assert selection["effective_keywords"] == ["爱玛"]\n        assert selection["keyword_packs"] == [{"id": pack_id, "version": 2}]\n        assert persisted_job["payload"]["keyword_selection"] == selection\n        assert persisted_job["payload"]["relevance"] is None''',
)

print("multi keyword pack corrective patch applied")
