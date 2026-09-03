"""一次性把 CHG-314 的 AI Analysis Run 扩展为 selected / all。

本脚本只用于当前 Change 分支的受控 Runner；Green 验证完成后必须删除。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} anchors, got {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def replace_in_section(path: str, start: str, end: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    section = text[start_index:end_index]
    count = section.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: section expected one anchor, got {count}: {old!r}")
    section = section.replace(old, new, 1)
    target.write_text(text[:start_index] + section + text[end_index:], encoding="utf-8")


def patch_contract() -> None:
    path = "backend/src/aima_ugc/contracts/http.py"
    replace_once(
        path,
        '''class AnalysisRunTargetSelection(BaseModel):
    """本轮只开放有容量上限的显式 Analysis Run 目标。"""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["selected"] = "selected"
    content_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_unique_content_ids(self) -> AnalysisRunTargetSelection:
        if len(self.content_ids) != len(set(self.content_ids)):
            raise ValueError("content_ids 不能重复")
        return self
''',
        '''class AnalysisRunTargetSelection(BaseModel):
    """正式 Analysis Run 支持显式选择或全部当前 Content。"""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["selected", "all"] = "selected"
    content_ids: tuple[UUID, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def validate_scope(self) -> AnalysisRunTargetSelection:
        if self.scope == "selected":
            if not self.content_ids:
                raise ValueError("selected 必须提供 1—1000 个 content_ids")
        elif self.content_ids:
            raise ValueError("all 不能提供 content_ids")
        if len(self.content_ids) != len(set(self.content_ids)):
            raise ValueError("content_ids 不能重复")
        return self
''',
    )
    replace_in_section(
        path,
        "class AnalysisContentRunResponse(BaseModel):",
        "class AnalysisContentRunCreatedResponse(BaseModel):",
        '    scope: Literal["query", "selected"]\n',
        '    scope: Literal["query", "selected", "all"]\n',
    )


def patch_content_http() -> None:
    path = "backend/src/aima_ugc/bootstrap/content_http.py"
    replace_once(
        path,
        '''        shard_size = self._runtime.settings.analysis_run_shard_size
        filter_snapshot = _analysis_filter_snapshot(targets)
        session = self._runtime.database.new_session()
''',
        '''        shard_size = self._runtime.settings.analysis_run_shard_size
        filter_snapshot = _analysis_filter_snapshot(targets)
        storage_scope = _analysis_run_storage_scope(targets)
        session = self._runtime.database.new_session()
''',
    )
    replace_count(path, "                        scope=targets.scope,\n", "                        scope=storage_scope,\n", 2)
    replace_once(path, "                    scope=targets.scope,\n", "                    scope=storage_scope,\n")
    replace_once(
        path,
        '''        if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
            return repository.freeze_target_statement(
                filters=targets.filters or ContentFilterSnapshot()
            )
        return repository.freeze_target_statement(content_ids=targets.content_ids)
''',
        '''        if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
            return repository.freeze_target_statement(filters=ContentFilterSnapshot())
        if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
            return repository.freeze_target_statement(
                filters=targets.filters or ContentFilterSnapshot()
            )
        return repository.freeze_target_statement(content_ids=targets.content_ids)
''',
    )
    replace_once(
        path,
        '''def _analysis_filter_snapshot(targets: _AnalysisTargetSelection) -> dict[str, object]:
    if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
        return (targets.filters or ContentFilterSnapshot()).model_dump(mode="json")
    return {"content_ids": [str(item) for item in targets.content_ids]}


def _analysis_configuration_hash(
''',
        '''def _analysis_filter_snapshot(targets: _AnalysisTargetSelection) -> dict[str, object]:
    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return {}
    if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
        return (targets.filters or ContentFilterSnapshot()).model_dump(mode="json")
    return {"content_ids": [str(item) for item in targets.content_ids]}


def _analysis_run_storage_scope(
    targets: _AnalysisTargetSelection,
) -> Literal["query", "selected"]:
    """公共 all 复用现有 query + 空筛选的持久语义，避免数据库迁移。"""

    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return "query"
    return cast(Literal["query", "selected"], targets.scope)


def _analysis_run_public_scope(row: RowMapping) -> Literal["query", "selected", "all"]:
    """把内部 query + 空筛选安全投影为公共 all，同时保留历史过滤 query。"""

    scope = cast(str, row["scope"])
    snapshot = cast(dict[str, object], row["filter_snapshot"])
    if scope == "query" and not snapshot:
        return "all"
    if scope in {"query", "selected"}:
        return cast(Literal["query", "selected"], scope)
    raise ValueError(f"未知 Analysis Run scope: {scope}")


def _analysis_configuration_hash(
''',
    )
    replace_once(
        path,
        '        scope=cast(Literal["query", "selected"], row["scope"]),\n',
        '        scope=_analysis_run_public_scope(row),\n',
    )


def patch_frontend_store() -> None:
    path = "frontend/src/features/voice-plaza/store.ts"
    replace_once(
        path,
        '''  function analysisTargetSelection(): AnalysisRunTargetSelection {
    return { scope: 'selected', content_ids: [...selectedIds.value] }
  }
''',
        '''  function analysisTargetSelection(scope: 'selected' | 'all'): AnalysisRunTargetSelection {
    return scope === 'all'
      ? { scope: 'all' }
      : { scope: 'selected', content_ids: [...selectedIds.value] }
  }
''',
    )
    replace_once(
        path,
        '''  async function previewAnalysis(
    _scope: 'selected',
  ): Promise<AnalysisContentRunPreviewResponse | null> {
    if (analysisConfigured.value !== true) {
      error.value = '当前环境尚未配置可用的 AI 模型，请配置 LLM 后重启后端。'
      return null
    }
    if (selectedIds.value.length === 0) return null
    if (selectedIds.value.length > 1000) {
      error.value = '单次 AI Analysis Run 最多选择 1000 条内容。'
      return null
    }
    previewingAnalysis.value = true
    error.value = null
    analysisPreview.value = null
    const targets = analysisTargetSelection()
    try {
      const preview = await previewAnalysisRun({ targets })
      analysisDraft = {
        targets,
        clientIdempotencyKey: crypto.randomUUID(),
      }
      analysisPreview.value = preview
      return preview
    } catch (reason) {
      analysisDraft = null
      error.value = errorMessage(reason)
      return null
    } finally {
      previewingAnalysis.value = false
    }
  }
''',
        '''  async function previewAnalysis(
    scope: 'selected' | 'all',
  ): Promise<AnalysisContentRunPreviewResponse | null> {
    if (analysisConfigured.value !== true) {
      error.value = '当前环境尚未配置可用的 AI 模型，请配置 LLM 后重启后端。'
      return null
    }
    if (scope === 'selected') {
      if (selectedIds.value.length === 0) return null
      if (selectedIds.value.length > 1000) {
        error.value = '单次 AI Analysis Run 最多选择 1000 条内容。'
        return null
      }
    }
    previewingAnalysis.value = true
    error.value = null
    analysisPreview.value = null
    const targets = analysisTargetSelection(scope)
    try {
      const preview = await previewAnalysisRun({ targets })
      analysisDraft = {
        targets,
        clientIdempotencyKey: crypto.randomUUID(),
      }
      analysisPreview.value = preview
      return preview
    } catch (reason) {
      analysisDraft = null
      error.value = errorMessage(reason)
      return null
    } finally {
      previewingAnalysis.value = false
    }
  }
''',
    )


def patch_analysis_dialog() -> None:
    path = ROOT / "frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/AnalysisSubmitDialog.vue"
    path.write_text(
        '''<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AnalysisContentRunPreviewResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  preview: AnalysisContentRunPreviewResponse | null
  previewing: boolean
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  preview: [scope: 'selected' | 'all']
  submit: []
}>()
const scope = ref<'selected' | 'all'>('all')
const selectedAvailable = computed(() => props.selectedCount > 0 && props.selectedCount <= 1000)

function chooseScope(next: 'selected' | 'all'): void {
  if (next === 'selected' && !selectedAvailable.value) return
  scope.value = next
  emit('preview', next)
}

watch(() => props.modelValue, (open) => {
  if (!open) return
  const initial: 'selected' | 'all' = selectedAvailable.value ? 'selected' : 'all'
  scope.value = initial
  emit('preview', initial)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="modal-layer"
    >
      <button
        class="backdrop"
        type="button"
        aria-label="关闭 AI 打标弹窗"
        @click="emit('update:modelValue', false)"
      />
      <section
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-title"
      >
        <header>
          <div>
            <h2 id="analysis-title">
              创建 AI Analysis Run
            </h2>
            <p>选择打标范围，预检后由后台冻结目标并拆分有界 Shard。</p>
          </div>
          <button
            class="close-button"
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            <AimaIcon
              name="close"
              :size="20"
            />
          </button>
        </header>
        <div class="body">
          <div
            class="scope-options"
            role="radiogroup"
            aria-label="AI 打标范围"
          >
            <button
              class="scope-option"
              :class="{ 'scope-option--active': scope === 'all' }"
              type="button"
              role="radio"
              :aria-checked="scope === 'all'"
              @click="chooseScope('all')"
            >
              <strong>全部数据</strong>
              <small>当前数据库全部 Content Current；不受声音广场当前筛选条件影响。</small>
            </button>
            <button
              class="scope-option"
              :class="{ 'scope-option--active': scope === 'selected' }"
              type="button"
              role="radio"
              :aria-checked="scope === 'selected'"
              :disabled="!selectedAvailable"
              @click="chooseScope('selected')"
            >
              <strong>已选内容</strong>
              <small v-if="selectedCount === 0">当前未选择内容。</small>
              <small v-else-if="selectedCount > 1000">已选 {{ selectedCount }} 条；显式选择模式最多 1000 条。</small>
              <small v-else>已选 {{ selectedCount }} 条；按当前 Content Version 冻结。</small>
            </button>
          </div>
          <p class="scope-note">
            全部数据模式不会把全量 Content ID 传到浏览器或 HTTP Payload；目标由服务端数据库计数并由 Planner 冻结。
          </p>
          <p class="cost-note">
            此操作可能产生模型调用费用。只有点击确认后才会创建 Analysis Run；导入和采集不会自动触发付费分析。
          </p>
          <div
            v-if="previewing"
            class="preview"
            role="status"
          >
            正在预检目标与模型配置…
          </div>
          <div
            v-else-if="preview"
            class="preview"
          >
            <strong>预检目标 {{ preview.target_count }} 条，拆分 {{ preview.shard_count }} 个 Shard</strong>
            <span>每个 Shard {{ preview.shard_size }} 条 · {{ preview.model_provider }} / {{ preview.model }}</span>
            <span>Prompt {{ preview.prompt_version }} · 配置哈希 {{ preview.configuration_hash.slice(0, 12) }}…</span>
            <small>{{ preview.cost_estimate_note }}</small>
          </div>
        </div>
        <footer>
          <AimaButton @click="emit('update:modelValue', false)">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="previewing || !preview || submitting || (scope === 'selected' && !selectedAvailable)"
            @click="emit('submit')"
          >
            {{ submitting ? '正在提交…' : '确认并创建 Analysis Run' }}
          </AimaButton>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-layer { position: fixed; z-index: 130; inset: 0; display: grid; place-items: center; }
.backdrop { position: absolute; inset: 0; border: 0; background: rgb(25 32 45 / 46%); }
.modal { position: relative; display: grid; width: min(580px, calc(100vw - 32px)); height: min(500px, calc(100vh - 32px)); overflow: hidden; border-radius: 11px; background: var(--aima-surface); box-shadow: 0 22px 58px rgb(20 28 42 / 22%); }
header { display: flex; min-height: 82px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
header p { margin: 5px 0 0; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.close-button { display: grid; width: 32px; height: 32px; place-items: center; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.body { display: grid; min-height: 0; align-content: start; gap: 10px; padding: 18px 22px 16px; overflow-y: auto; }
.scope-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.scope-option { display: grid; min-height: 76px; align-content: center; gap: 5px; padding: 11px 13px; border: 1px solid var(--aima-border); border-radius: 8px; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; text-align: left; }
.scope-option--active { border-color: var(--aima-primary); background: var(--aima-primary-soft); box-shadow: 0 0 0 1px var(--aima-primary-soft); }
.scope-option:disabled { cursor: not-allowed; opacity: .5; }
.scope-option strong { color: var(--aima-text); font-size: 12px; }
.scope-option small { color: var(--aima-text-muted); font-size: 10px; line-height: 15px; }
.scope-note { margin: 0; color: var(--aima-text-muted); font-size: 10px; line-height: 16px; }
.cost-note { margin: 0; padding: 8px 12px; border: 1px solid #f2d48a; border-radius: 6px; color: #b7791f; background: #fff9e9; font-size: 10px; line-height: 17px; }
.preview { display: grid; min-height: 88px; align-content: center; gap: 5px; padding: 10px 12px; border: 1px solid #bfd5f5; border-radius: 6px; color: #32618f; background: #f2f7fd; font-size: 10px; line-height: 14px; }
.preview strong { font-size: 11px; }
.preview small { color: var(--aima-text-disabled); font-size: 9px; }
footer { display: flex; min-height: 68px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); }
footer :deep(.aima-button) { height: 38px; }
@media (min-height: 560px) {
  .modal { transform: translateY(-17px); }
}
</style>
''',
        encoding="utf-8",
    )


def patch_voice_plaza_page() -> None:
    path = "frontend/src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue"
    replace_once(
        path,
        '''          <AimaButton
            icon="ai"
            :disabled="store.selectedIds.length === 0 || store.selectedIds.length > 1000 || store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : store.selectedIds.length === 0 ? '请先选择需要打标的内容' : store.selectedIds.length > 1000 ? '单次最多选择 1000 条内容' : undefined"
            @click="analysisOpen = true"
          >
            AI 打标
          </AimaButton>
''',
        '''          <AimaButton
            icon="ai"
            :disabled="store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : undefined"
            @click="analysisOpen = true"
          >
            AI 打标
          </AimaButton>
''',
    )


def patch_frontend_unit_test() -> None:
    path = "frontend/tests/analysis-all-scope.spec.ts"
    replace_once(path, "    api.fetchContentAnalysisCapabilities.mockResolvedValue({ configured: true })\n", "    api.fetchContentAnalysisCapabilities.mockResolvedValue({ configured: true })\n    api.fetchAnalysisRuns.mockResolvedValue({ items: [] })\n    api.submitAnalysisRun.mockResolvedValue({\n      run_id: '62345678-1234-5678-1234-567812345678',\n      planner_job_id: '52345678-1234-5678-1234-567812345678',\n      target_count: 4200,\n      shard_count: 42,\n      status: 'queued',\n    })\n")
    replace_once(path, "    const preview = await store.previewAnalysis('all' as never)\n", "    const preview = await store.previewAnalysis('all')\n")
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    marker = "submits all current data without content_ids"
    if marker not in text:
        text = text.replace(
            "\n  it('keeps selected mode validation independent from all mode', async () => {",
            '''\n  it('submits all current data without content_ids', async () => {
    const store = useVoicePlazaStore()
    await store.refreshAnalysisCapabilities()
    await store.previewAnalysis('all')

    const count = await store.confirmAnalysis()

    expect(count).toBe(4200)
    expect(api.submitAnalysisRun).toHaveBeenCalledWith(expect.objectContaining({
      expected_target_count: 4200,
      targets: { scope: 'all' },
    }))
  })

  it('keeps selected mode validation independent from all mode', async () => {''',
            1,
        )
    target.write_text(text, encoding="utf-8")


def patch_backend_contract_test() -> None:
    path = "tests/api/test_frontend_reliability_contracts.py"
    replace_once(path, "from uuid import UUID, uuid4\n\n", "from uuid import UUID, uuid4\n\nimport pytest\nfrom pydantic import ValidationError\n\n")
    replace_once(
        path,
        '''from aima_ugc.contracts.http import (
    HistoricalCampaignResponse,
''',
        '''from aima_ugc.contracts.http import (
    AnalysisRunTargetSelection,
    HistoricalCampaignResponse,
''',
    )
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    marker = "test_analysis_run_all_scope_has_no_content_id_payload"
    if marker not in text:
        text += '''


def test_analysis_run_all_scope_has_no_content_id_payload() -> None:
    targets = AnalysisRunTargetSelection(scope="all")

    assert targets.scope == "all"
    assert targets.content_ids == ()

    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(scope="all", content_ids=(uuid4(),))

    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(scope="selected")
'''
    target.write_text(text, encoding="utf-8")


def patch_postgres_integration_test() -> None:
    path = ROOT / "tests/integration/content/test_stage12_analysis_runs.py"
    text = path.read_text(encoding="utf-8")
    marker = "test_analysis_all_scope_freezes_every_current_content_without_id_payload"
    if marker in text:
        raise RuntimeError("AI all-scope PostgreSQL test already exists")
    insertion = '''


def test_analysis_all_scope_freezes_every_current_content_without_id_payload(
    tmp_path: Path,
) -> None:
    settings = load_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "log_dir": tmp_path / "logs",
            "llm_base_url": "https://fake.example/v1",
            "llm_provider_name": "fake",
            "llm_model": "fake-content-labeler-v1",
            "analysis_run_shard_size": 1,
            "analysis_run_max_in_flight_jobs": 2,
        }
    )
    runtime = create_worker_runtime(settings=settings)
    with runtime.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts, audit_events "
            "RESTART IDENTITY CASCADE"
        )
    try:
        content_service = PostgresContentHttpService(
            runtime,
            cursor_signing_secret=b"stage12-analysis-cursor-key-32-bytes",
        )
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                content_service=content_service,
            )
        )
        _seed_contents(client)
        import_worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="stage12-analysis-all-import",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert import_worker.run_once() is True
        with runtime.database.engine.begin() as connection:
            assert connection.scalar(select(func.count()).select_from(contents_table)) == 3

        preview = client.post(
            "/api/v1/analysis/content-runs/preview",
            json={"targets": {"scope": "all"}},
        )
        assert preview.status_code == 200
        assert preview.json()["target_count"] == 3
        assert preview.json()["shard_count"] == 3

        created = client.post(
            "/api/v1/analysis/content-runs",
            json={
                "client_idempotency_key": "stage12-analysis-all",
                "targets": {"scope": "all"},
                "expected_target_count": 3,
                "expected_configuration_hash": preview.json()["configuration_hash"],
                "run_intent": "manual_reanalysis",
            },
        )
        assert created.status_code == 202
        run_id = UUID(created.json()["run_id"])
        with runtime.database.engine.begin() as connection:
            row = (
                connection.execute(
                    select(
                        analysis_content_runs_table.c.scope,
                        analysis_content_runs_table.c.filter_snapshot,
                    ).where(analysis_content_runs_table.c.id == run_id)
                )
                .mappings()
                .one()
            )
            assert row["scope"] == "query"
            assert row["filter_snapshot"] == {}
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_run_targets_table)
                )
                == 0
            )

        planner_worker = create_job_worker(
            runtime=runtime,
            registry=_analysis_registry(runtime, sentiment="中性"),
            worker_id="stage12-analysis-all-planner",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert planner_worker.run_once() is True
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_run_targets_table)
                )
                == 3
            )
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_requests_table)
                )
                == 2
            )
        run = client.get(f"/api/v1/analysis/content-runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["scope"] == "all"
        assert run.json()["target_count"] == 3
    finally:
        runtime.close()
'''
    anchor = "\n\ndef test_analysis_planner_rolls_back_when_frozen_selection_count_changed"
    if anchor not in text:
        raise RuntimeError("stage12 analysis test insertion anchor missing")
    path.write_text(text.replace(anchor, insertion + anchor, 1), encoding="utf-8")


def patch_browser_acceptance() -> None:
    path = ROOT / "frontend/e2e/analysis-all-scope.spec.ts"
    path.write_text(
        '''import { expect, test } from './fixture'

import { stubVoicePlazaTaxonomy } from './voicePlazaTaxonomy'

const contentId = '42345678-1234-5678-1234-567812345678'
const runId = '62345678-1234-5678-1234-567812345678'
const plannerJobId = '52345678-1234-5678-1234-567812345678'

const item = {
  id: contentId,
  content_version: 1,
  platform: 'xiaohongshu',
  external_content_id: 'note-all-scope-1',
  content_type: 'note',
  title: '全部数据打标验证',
  text: '固定浏览器黑盒数据',
  author_display_name: '测试用户',
  published_at: '2026-09-03T08:00:00+08:00',
  last_seen_at: '2026-09-03T08:10:00+08:00',
  content_url: 'https://example.com/all-scope',
  metrics: {},
  analysis: {
    status: 'pending',
    relevance: null,
    voice_type: null,
    sentiment: null,
    labels: [],
    analyzed_at: null,
    model_provider: null,
    model: null,
    latest_run_id: null,
    latest_run_status: null,
    manual_locked_dimensions: [],
  },
  effective_relevance: null,
  relevance_source: null,
  source: { provider_name: 'file-import' },
  vehicles: [],
  availability: null,
}

test('creates an all-data AI Run without selecting rows or sending content ids', async ({ page }) => {
  await stubVoicePlazaTaxonomy(page)
  let previewBody: unknown = null
  let createBody: unknown = null

  await page.route('**/api/v1/content-analysis-capabilities', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ configured: true }) })
  })
  await page.route('**/api/v1/contents**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [item], next_cursor: null, has_more: false }),
    })
  })
  await page.route('**/api/v1/data-exports', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })
  await page.route('**/api/v1/analysis/content-runs**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/analysis/content-runs/preview') {
      previewBody = request.postDataJSON()
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          target_count: 4200,
          shard_count: 42,
          shard_size: 100,
          analysis_scheme_version_id: null,
          prompt_version: 'content_labeling_v3',
          prompt_sha256: 'a'.repeat(64),
          taxonomy_sha256: 'b'.repeat(64),
          model_provider: 'local',
          model: 'deepseek',
          generation_config: {},
          generation_config_hash: 'c'.repeat(64),
          configuration_hash: 'd'.repeat(64),
          cost_estimate_available: false,
          cost_estimate_note: '运行后以真实审计为准。',
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/analysis/content-runs' && request.method() === 'POST') {
      createBody = request.postDataJSON()
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: runId,
          planner_job_id: plannerJobId,
          target_count: 4200,
          shard_count: 42,
          status: 'queued',
        }),
      })
      return
    }
    if (url.pathname === '/api/v1/analysis/content-runs' && request.method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [] }) })
      return
    }
    await route.fallback()
  })

  await page.goto('/voice-plaza')
  const aiButton = page.getByRole('button', { name: 'AI 打标', exact: true })
  await expect(aiButton).toBeEnabled()
  await aiButton.click()

  await expect(page.getByRole('radio', { name: /全部数据/ })).toHaveAttribute('aria-checked', 'true')
  await expect(page.getByText('预检目标 4200 条，拆分 42 个 Shard')).toBeVisible()
  expect(previewBody).toEqual({ targets: { scope: 'all' } })

  await page.getByRole('button', { name: '确认并创建 Analysis Run', exact: true }).click()
  expect(createBody).toEqual(expect.objectContaining({
    targets: { scope: 'all' },
    expected_target_count: 4200,
  }))
  await expect(page.getByText('已创建 AI Analysis Run，冻结 4200 条内容。')).toBeVisible()
})
''',
        encoding="utf-8",
    )


def patch_docs() -> None:
    appendix = ROOT / "docs/appendix/07_AI舆情打标与分析实现.md"
    text = appendix.read_text(encoding="utf-8")
    marker = "## Analysis Run 的 selected / all 范围"
    if marker not in text:
        text += '''

---

## Analysis Run 的 selected / all 范围

声音广场正式 Analysis Run 提供两种用户范围：

```text
selected
→ 显式 1—1000 个 Content ID

all
→ 当前数据库中的全部 Content Current
→ 不受声音广场当前筛选条件影响
→ HTTP 请求不携带全量 Content ID
```

`all` 在公共 HTTP Contract 中是独立 Scope；持久化层继续复用既有 `analysis_content_runs.scope = query` + 空 `filter_snapshot`，因此不需要数据库 Migration。读取 Run 时，空筛选的内部 `query` 投影为公共 `all`；历史存在实际筛选条件的 `query` Run 仍按 `query` 返回，避免错误改写历史语义。

Preview 只做数据库集合式计数和 Analysis 配置冻结预检。Create 只创建 Run Header + Planner Job；Planner 再用集合式 `INSERT ... SELECT` 冻结 `content_id + current_version`，并按既有 `analysis_run_shard_size / analysis_run_max_in_flight_jobs` 有界创建 Shard。禁止前端先分页拉取全部 ID，也禁止把全量目标塞进一个 Job Payload。
'''
        appendix.write_text(text, encoding="utf-8")

    readme = ROOT / "backend/src/aima_ugc/modules/analysis/README.md"
    text = readme.read_text(encoding="utf-8")
    marker = "### Analysis Run 用户范围"
    if marker not in text:
        text += '''

---

### Analysis Run 用户范围

正式 Run 的公共 Scope 为：

- `selected`：1—1000 个显式 Content ID；
- `all`：数据库全部 Content Current，不受当前页面筛选影响，也不在 HTTP/浏览器传输全量 ID。

`all` 内部复用已有 `query + 空 filter_snapshot` 的持久语义，由 Planner 集合式冻结并按现有 Shard 窗口执行，因此不新增表或 Migration。历史带实际筛选条件的 `query` Run 保留原语义。
'''
        readme.write_text(text, encoding="utf-8")


def main() -> None:
    patch_contract()
    patch_content_http()
    patch_frontend_store()
    patch_analysis_dialog()
    patch_voice_plaza_page()
    patch_frontend_unit_test()
    patch_backend_contract_test()
    patch_postgres_integration_test()
    patch_browser_acceptance()
    patch_docs()


if __name__ == "__main__":
    main()
