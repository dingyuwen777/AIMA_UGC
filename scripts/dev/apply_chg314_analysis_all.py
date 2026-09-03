"""一次性应用 CHG-314 AI 全部数据 Analysis Run 补丁。

该脚本只用于当前远程开发分支，Green 验证完成后必须删除。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    """对一个稳定锚点做一次精确替换，避免静默误改。"""

    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, *, expected: int) -> None:
    """对已知重复锚点按精确数量替换。"""

    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} anchors, got {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def patch_contract() -> None:
    """公开 selected/all Scope，同时保持历史 query Run 响应兼容。"""

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
    """Analysis Run 公开目标：显式选择或数据库当前全部 Content。"""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["selected", "all"] = "selected"
    content_ids: tuple[UUID, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def validate_scope_and_content_ids(self) -> AnalysisRunTargetSelection:
        if len(self.content_ids) != len(set(self.content_ids)):
            raise ValueError("content_ids 不能重复")
        if self.scope == "selected" and not self.content_ids:
            raise ValueError("selected Scope 必须提供至少一个 content_id")
        if self.scope == "all" and self.content_ids:
            raise ValueError("all Scope 不能提交 content_ids")
        return self
''',
    )
    replace_once(
        path,
        '    scope: Literal["query", "selected"]\n    target_count: int = Field(gt=0)\n',
        '    scope: Literal["all", "query", "selected"]\n    target_count: int = Field(gt=0)\n',
    )


def patch_content_service() -> None:
    """把公开 all 规范化为现有 DB query+空过滤语义，并安全投影回 all。"""

    path = "backend/src/aima_ugc/bootstrap/content_http.py"
    replace_once(
        path,
        '''        filter_snapshot = _analysis_filter_snapshot(targets)
        session = self._runtime.database.new_session()
''',
        '''        filter_snapshot = _analysis_filter_snapshot(targets)
        storage_scope = _analysis_storage_scope(targets)
        session = self._runtime.database.new_session()
''',
    )
    replace_count(path, "                        scope=targets.scope,\n", "                        scope=storage_scope,\n", expected=2)
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


''',
        '''def _analysis_filter_snapshot(targets: _AnalysisTargetSelection) -> dict[str, object]:
    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return ContentFilterSnapshot().model_dump(mode="json")
    if isinstance(targets, ContentTargetSelection) and targets.scope == "query":
        return (targets.filters or ContentFilterSnapshot()).model_dump(mode="json")
    return {"content_ids": [str(item) for item in targets.content_ids]}


def _analysis_storage_scope(targets: _AnalysisTargetSelection) -> Literal["query", "selected"]:
    """公开 all 复用数据库既有 query Scope，避免无意义 Schema Migration。"""

    if isinstance(targets, AnalysisRunTargetSelection) and targets.scope == "all":
        return "query"
    return cast(Literal["query", "selected"], targets.scope)


def _analysis_response_scope(row: RowMapping) -> Literal["all", "query", "selected"]:
    """空过滤 query 等价于全部当前 Content；历史有过滤 query 继续原样返回。"""

    stored_scope = cast(Literal["query", "selected"], row["scope"])
    if (
        stored_scope == "query"
        and row["filter_snapshot"] == ContentFilterSnapshot().model_dump(mode="json")
    ):
        return "all"
    return stored_scope


''',
    )
    replace_once(
        path,
        '        scope=cast(Literal["query", "selected"], row["scope"]),\n',
        '        scope=_analysis_response_scope(row),\n',
    )


def patch_frontend_store() -> None:
    """让 Store 在无显式选择时也能预检 all，且 all Payload 不携带 ID。"""

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
''',
        '''  async function previewAnalysis(
    scope: 'selected' | 'all',
  ): Promise<AnalysisContentRunPreviewResponse | null> {
    if (analysisConfigured.value !== true) {
      error.value = '当前环境尚未配置可用的 AI 模型，请配置 LLM 后重启后端。'
      return null
    }
    if (scope === 'selected' && selectedIds.value.length === 0) return null
    if (scope === 'selected' && selectedIds.value.length > 1000) {
      error.value = '单次 AI Analysis Run 最多选择 1000 条内容。'
      return null
    }
    previewingAnalysis.value = true
    error.value = null
    analysisPreview.value = null
    const targets = analysisTargetSelection(scope)
''',
    )


def patch_voice_page() -> None:
    """AI 按钮只依赖 Runtime；目标范围由弹窗显式选择。"""

    path = "frontend/src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue"
    replace_once(
        path,
        ''':disabled="store.selectedIds.length === 0 || store.selectedIds.length > 1000 || store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : store.selectedIds.length === 0 ? '请先选择需要打标的内容' : store.selectedIds.length > 1000 ? '单次最多选择 1000 条内容' : undefined"
''',
        ''':disabled="store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : '可选择已选内容或全部数据进行打标'"
''',
    )


def patch_tests() -> None:
    """补齐 PostgreSQL、Browser Mock 和既有测试对 all Scope 的验证。"""

    replace_once(
        "frontend/tests/analysis-all-scope.spec.ts",
        "    const preview = await store.previewAnalysis('all' as never)\n",
        "    const preview = await store.previewAnalysis('all')\n",
    )

    path = "tests/integration/content/test_stage12_analysis_runs.py"
    anchor = '''def test_analysis_planner_rolls_back_when_frozen_selection_count_changed(tmp_path: Path) -> None:
'''
    test = '''def test_analysis_all_scope_reuses_query_storage_and_freezes_all_current_contents(
    tmp_path: Path,
) -> None:
    """公开 all 不搬运 ID，并复用 query 存储语义冻结全部当前 Content。"""

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
        client = TestClient(
            create_app(
                import_service=PostgresImportHttpService(runtime),
                content_service=PostgresContentHttpService(
                    runtime,
                    cursor_signing_secret=b"stage12-analysis-cursor-key-32-bytes",
                ),
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

        preview = client.post(
            "/api/v1/analysis/content-runs/preview",
            json={"targets": {"scope": "all"}},
        )
        assert preview.status_code == 200
        assert preview.json()["target_count"] == 3
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
            stored = connection.execute(
                select(
                    analysis_content_runs_table.c.scope,
                    analysis_content_runs_table.c.filter_snapshot,
                ).where(analysis_content_runs_table.c.id == run_id)
            ).one()
            assert stored.scope == "query"
            assert "content_ids" not in stored.filter_snapshot
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_run_targets_table)
                )
                == 0
            )

        assert _drain_analysis(runtime, sentiment="中性", worker_id="stage12-analysis-all") == 4
        run = client.get(f"/api/v1/analysis/content-runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["scope"] == "all"
        assert run.json()["status"] == "succeeded"
        assert run.json()["stats"]["succeeded"] == 3
        with runtime.database.engine.begin() as connection:
            assert (
                connection.scalar(
                    select(func.count()).select_from(analysis_content_run_targets_table)
                )
                == 3
            )
    finally:
        runtime.close()


'''
    replace_once(path, anchor, test + anchor)

    path = "frontend/e2e/voice-plaza.spec.ts"
    replace_once(
        path,
        "  await expect(analysisButton).toBeDisabled()\n  await page.getByLabel('选择当前已加载内容').check()\n",
        "  await expect(analysisButton).toBeEnabled()\n  await page.getByLabel('选择当前已加载内容').check()\n",
    )
    new_test = '''
test('creates an all-data analysis run without browser-side content ids', async ({ page }) => {
  let previewRequest: Record<string, unknown> | undefined
  let createRequest: Record<string, unknown> | undefined
  await page.route('**/api/v1/analysis/content-runs/preview', async (route) => {
    previewRequest = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        target_count: 4200,
        shard_count: 42,
        shard_size: 100,
        prompt_version: 'content_labeling_v3',
        prompt_sha256: 'a'.repeat(64),
        taxonomy_sha256: 'b'.repeat(64),
        model_provider: 'openai-compatible',
        model: 'fixture-model',
        generation_config: { temperature: 0 },
        generation_config_hash: 'c'.repeat(64),
        configuration_hash: 'd'.repeat(64),
        cost_estimate_available: false,
        cost_estimate_note: '运行后以实际 token/cost 审计为准。',
      }),
    })
  })
  await page.route('**/api/v1/analysis/content-runs', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    createRequest = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: analysisRunId,
        planner_job_id: analysisJobId,
        target_count: 4200,
        shard_count: 42,
        status: 'queued',
      }),
    })
  })

  await page.goto('/voice-plaza')
  const analysisButton = page.getByRole('button', { name: /AI 打标/ })
  await expect(analysisButton).toBeEnabled()
  await analysisButton.click()
  const dialog = page.getByRole('dialog', { name: '创建 AI Analysis Run' })
  await expect(dialog.getByRole('radio', { name: /全部数据/ })).toBeChecked()
  await expect(dialog.getByText('预检目标 4200 条，拆分 42 个 Shard')).toBeVisible()
  expect(previewRequest).toEqual({ targets: { scope: 'all' } })
  await dialog.getByRole('button', { name: '确认并创建 Analysis Run' }).click()
  expect(createRequest).toMatchObject({
    targets: { scope: 'all' },
    expected_target_count: 4200,
    expected_configuration_hash: 'd'.repeat(64),
  })
})

'''
    replace_once(
        path,
        "test('keeps export history visible but disables empty query export creation', async ({ page }) => {\n",
        new_test
        + "test('keeps export history visible but disables empty query export creation', async ({ page }) => {\n",
    )
    replace_once(
        path,
        "  await expect(page.getByRole('button', { name: /AI 打标/ })).toBeDisabled()\n  await page.getByRole('button', { name: /导出记录/ }).click()\n",
        "  await expect(page.getByRole('button', { name: /AI 打标/ })).toBeEnabled()\n  await page.getByRole('button', { name: /导出记录/ }).click()\n",
    )


def main() -> None:
    """按 Contract → Service → Frontend → Tests 的顺序应用补丁。"""

    patch_contract()
    patch_content_service()
    patch_frontend_store()
    patch_voice_page()
    patch_tests()


if __name__ == "__main__":
    main()
