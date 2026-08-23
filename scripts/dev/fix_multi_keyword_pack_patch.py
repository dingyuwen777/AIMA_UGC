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


# Stage 8E API fake/fixtures 跟随新请求 Contract；响应仍返回冻结后的有效关键词。
path = "tests/api/test_stage8e_collection_runs.py"
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
    '            "keyword_pack_ids": [str(uuid4())],\n            "stats": {',
    '            "keywords": ["爱玛", "爱玛 Q7"],\n            "stats": {',
)
replace_once(
    path,
    '''        json={
            "mode": "discovery",
            "keyword_pack_ids": [str(uuid4())],
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],''',
    '''        json={
            "mode": "discovery",
            "keyword_pack_ids": [str(PACK_ID)],
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],''',
)
replace_once(
    path,
    '''        json={
            "mode": "batch_supplement",
            "keyword_pack_ids": [str(uuid4())],
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],''',
    '''        json={
            "mode": "batch_supplement",
            "keyword_pack_ids": [str(PACK_ID)],
            "import_batch_id": str(BATCH_ID),
            "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(CONFIG_ID)}],''',
)

# Stage 8B PostgreSQL integration：上传显式携带所选词包；断言新冻结快照。
path = "tests/integration/ingestion/test_stage8b_import_http_worker.py"
replace_once(
    path,
    '''        files={
            "file": (
                "stage8b.xlsx",
                _xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },''',
    '''        files=[
            (
                "file",
                (
                    "stage8b.xlsx",
                    _xlsx(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("keyword_pack_ids", (None, pack_id)),
        ],''',
)
replace_once(
    path,
    '''        assert persisted_batch["stats"]["relevance"]["effective_keywords"] == ["爱玛"]
        assert persisted_job["payload"]["relevance"] == persisted_batch["stats"]["relevance"]''',
    '''        selection = persisted_batch["stats"]["keyword_selection"]
        assert selection["effective_keywords"] == ["爱玛"]
        assert len(selection["keyword_packs"]) == 1
        assert selection["keyword_packs"][0]["version"] == 2
        assert persisted_job["payload"]["keyword_selection"] == selection
        assert persisted_job["payload"]["relevance"] is None''',
)

# Frontend runtime tests：请求改为 keyword_pack_ids，且 Store 新增启用词包读取依赖。
path = "frontend/tests/collection-runtime.spec.ts"
replace_once(
    path,
    '''  listImportBatches: vi.fn(),
  getImportBatch: vi.fn(),''',
    '''  listImportBatches: vi.fn(),
  listKeywordPacks: vi.fn(),
  getImportBatch: vi.fn(),''',
)
replace_once(
    path,
    '''    generated.getCollectionBatchSupplementEligibility.mockImplementation(async (batchId: string) => ({
      batch_id: batchId,
      targets: [],
    }))''',
    '''    generated.getCollectionBatchSupplementEligibility.mockImplementation(async (batchId: string) => ({
      batch_id: batchId,
      targets: [],
    }))
    generated.listKeywordPacks.mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 100,
    })''',
)
replace_once(
    path,
    '''    await createTikHubCollectionRun({
      mode: 'discovery', keywords: ['爱玛', 'Q7'],
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      include_comments: true, include_sub_comments: false,
    })
    expect(generated.createCollectionRun).toHaveBeenCalledWith(expect.objectContaining({ mode: 'discovery', keywords: ['爱玛', 'Q7'] }))''',
    '''    await createTikHubCollectionRun({
      mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'],
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      include_comments: true, include_sub_comments: false,
    })
    expect(generated.createCollectionRun).toHaveBeenCalledWith(
      expect.objectContaining({ mode: 'discovery', keyword_pack_ids: ['pack-1', 'pack-2'] }),
    )''',
)

print("multi keyword pack corrective patch applied")
