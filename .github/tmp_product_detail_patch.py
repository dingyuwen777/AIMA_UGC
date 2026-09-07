from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return text.replace(old, new, 1)


detail_path = Path('frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue')
detail = detail_path.read_text(encoding='utf-8')

detail = replace_once(
    detail,
    "  return '正在补充完整详情与评论，当前先展示已入库内容。'\n}\n</script>",
    """  return '正在补充完整详情与评论，当前先展示已入库内容。'\n}\n\n/** 将标准化内容类型映射为业务文案，未知旧值不直接暴露内部枚举。 */\nfunction contentTypeLabel(value: string): string {\n  if (value === 'image') return '图文 / 图片'\n  if (value === 'video') return '视频'\n  if (value === 'text') return '纯文本'\n  return '未识别'\n}\n\n/** 将内部 Provider 名称归一为用户可理解的来源类别。 */\nfunction sourceLabel(providerName: string): string {\n  const normalized = providerName.toLowerCase()\n  if (normalized.includes('import') || normalized.includes('excel')) return '数据导入'\n  if (normalized.includes('tikhub')) return 'TikHub 采集'\n  if (normalized.includes('manual')) return '人工维护'\n  return '平台采集'\n}\n\n/** 将第三方可用状态映射为业务状态，原始 code 仅在技术详情保留。 */\nfunction availabilityLabel(status: string): string {\n  if (status === 'available') return '当前可访问'\n  if (status === 'unavailable_confirmed') return '已确认不可访问'\n  if (status === 'unavailable_suspected') return '可能不可访问'\n  return '状态待确认'\n}\n\n/** 将车型证据来源归一为用户语义；内部 source/catalog version 下沉技术详情。 */\nfunction vehicleEvidenceLabel(source: string): string {\n  const normalized = source.toLowerCase()\n  if (normalized.includes('manual')) return '人工确认'\n  if (normalized.includes('keyword') || normalized.includes('alias')) return '词包 / 别名识别'\n  return '系统识别'\n}\n\n/** 将评论覆盖枚举转换为用户可读状态。 */\nfunction commentCoverageLabel(value: string): string {\n  if (value === 'complete') return '完整'\n  if (value === 'partial') return '部分'\n  return '待确认'\n}\n</script>""",
    'insert product labels',
)

detail = replace_once(
    detail,
    """            <h2>内容详情</h2>\n            <small v-if=\"item\">Content ID: {{ item.id }}</small>""",
    """            <h2>内容详情</h2>\n            <small v-if=\"item\">{{ platformLabel(item.platform) }} · {{ item.author_display_name || '未知作者' }}</small>""",
    'header identity',
)

detail = replace_once(
    detail,
    """            <small v-if=\"item.analysis.analyzed_at\">分析时间：{{ formatDateTime(item.analysis.analyzed_at) }} · {{ item.analysis.model_provider }} / {{ item.analysis.model }}</small>""",
    """            <small v-if=\"item.analysis.analyzed_at\">分析时间：{{ formatDateTime(item.analysis.analyzed_at) }}</small>""",
    'analysis model details',
)

detail = replace_once(
    detail,
    """                  {{ evidence.source }}<template v-if=\"evidence.matched_text\"> · “{{ evidence.matched_text }}”</template> · catalog v{{ evidence.catalog_version }}<template v-if=\"evidence.is_manual_locked\"> · 人工锁定</template>""",
    """                  {{ vehicleEvidenceLabel(evidence.source) }}<template v-if=\"evidence.matched_text\"> · 命中“{{ evidence.matched_text }}”</template><template v-if=\"evidence.is_manual_locked\"> · 已人工确认</template>""",
    'vehicle evidence business projection',
)

detail = replace_once(
    detail,
    """              <div><h4>发声类型、情感与标签人工纠正</h4><small>合法值来自当前发布的原子 Analysis Scheme。</small></div>""",
    """              <div><h4>发声类型、情感与标签人工纠正</h4><small>合法选项来自当前生效的 AI 分析规则。</small></div>""",
    'analysis scheme wording',
)

detail = replace_once(
    detail,
    """          <section>\n            <h4>第三方可用状态</h4>\n            <p v-if=\"item.availability\">\n              {{ item.availability.status }} · {{ item.availability.reason_code }} · {{ item.availability.evidence_kind }} · {{ formatDateTime(item.availability.observed_at) }}\n            </p>\n            <p v-else>\n              unknown · 尚无明确 Provider 证据。技术失败不会直接标记为确认下架。\n            </p>\n          </section>""",
    """          <section>\n            <h4>内容可用状态</h4>\n            <p v-if=\"item.availability\">\n              {{ availabilityLabel(item.availability.status) }} · 更新于 {{ formatDateTime(item.availability.observed_at) }}\n            </p>\n            <p v-else>\n              状态待确认 · 暂无明确的平台可用性证据。\n            </p>\n          </section>""",
    'availability business projection',
)

detail = replace_once(
    detail,
    """              <div><dt>内容类型</dt><dd>{{ item.content_type }}</dd></div>\n              <div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div>\n              <div><dt>外部内容 ID</dt><dd>{{ item.external_content_id }}</dd></div>\n              <div><dt>来源</dt><dd>{{ item.source.provider_name }}</dd></div>""",
    """              <div><dt>内容类型</dt><dd>{{ contentTypeLabel(item.content_type) }}</dd></div>\n              <div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div>\n              <div><dt>来源</dt><dd>{{ sourceLabel(item.source.provider_name) }}</dd></div>""",
    'structured info business projection',
)

detail = replace_once(
    detail,
    """          </section>\n\n          <section>\n            <h4>互动数据</h4>""",
    """          </section>\n\n          <section class=\"technical-section\">\n            <details class=\"technical-details\">\n              <summary>技术详情</summary>\n              <dl>\n                <div><dt>Content ID</dt><dd>{{ item.id }}</dd></div>\n                <div><dt>外部内容 ID</dt><dd>{{ item.external_content_id }}</dd></div>\n                <div><dt>当前来源 Provider</dt><dd>{{ item.source.provider_name }}</dd></div>\n                <div><dt>Provider Attempt</dt><dd>{{ item.source.provider_attempt_id || '—' }}</dd></div>\n                <div><dt>Raw Artifact</dt><dd>{{ item.source.raw_artifact_id || '—' }}</dd></div>\n                <div><dt>Import Batch</dt><dd>{{ item.source.import_batch_id || '—' }}</dd></div>\n                <div><dt>Collection Run</dt><dd>{{ item.source.collection_run_id || '—' }}</dd></div>\n                <div><dt>AI 模型</dt><dd>{{ item.analysis.model_provider }} / {{ item.analysis.model }}</dd></div>\n                <div v-if=\"item.availability\"><dt>可用状态原始证据</dt><dd>{{ item.availability.status }} · {{ item.availability.reason_code }} · {{ item.availability.evidence_kind }}</dd></div>\n              </dl>\n              <div v-if=\"(item.source_records ?? []).length\" class=\"technical-list\">\n                <strong>来源追溯</strong>\n                <span\n                  v-for=\"(source, index) in item.source_records ?? []\"\n                  :key=\"`${source.provider_attempt_id ?? source.raw_artifact_id ?? index}`\"\n                >\n                  {{ source.provider_name }}<template v-if=\"source.import_batch_id\"> · Import {{ source.import_batch_id }}</template><template v-if=\"source.collection_run_id\"> · Run {{ source.collection_run_id }}</template><template v-if=\"source.provider_attempt_id\"> · Attempt {{ source.provider_attempt_id }}</template><template v-if=\"source.raw_artifact_id\"> · Artifact {{ source.raw_artifact_id }}</template>\n                </span>\n              </div>\n              <div v-if=\"(item.vehicles ?? []).some((vehicle) => vehicle.evidences.length)\" class=\"technical-list\">\n                <strong>车型证据追溯</strong>\n                <template v-for=\"vehicle in item.vehicles ?? []\" :key=\"vehicle.vehicle_model_id\">\n                  <span\n                    v-for=\"(evidence, index) in vehicle.evidences\"\n                    :key=\"`${vehicle.vehicle_model_id}:${index}`\"\n                  >{{ vehicle.display_name }} · {{ evidence.source }} · catalog v{{ evidence.catalog_version }}<template v-if=\"evidence.source_field\"> · {{ evidence.source_field }}</template></span>\n                </template>\n              </div>\n            </details>\n          </section>\n\n          <section>\n            <h4>互动数据</h4>""",
    'technical details section',
)

detail = replace_once(
    detail,
    """              已采集 {{ formatNumber(item.comment_coverage.collected_count) }} / {{ formatNumber(item.comment_coverage.reported_total) }}，覆盖状态：{{ item.comment_coverage.coverage }}""",
    """              已采集 {{ formatNumber(item.comment_coverage.collected_count) }} / {{ formatNumber(item.comment_coverage.reported_total) }}，覆盖状态：{{ commentCoverageLabel(item.comment_coverage.coverage) }}""",
    'comment coverage label',
)

detail = replace_once(
    detail,
    ".review-warning { padding: 8px 10px; border-radius: 5px; color: #8a641d !important; background: #fff9ec; }\ndl {",
    ".review-warning { padding: 8px 10px; border-radius: 5px; color: #8a641d !important; background: #fff9ec; }\n.technical-section { padding: 0 !important; border: 0 !important; background: transparent !important; }\n.technical-details { padding: 10px 12px; border: 1px dashed var(--aima-border-strong); border-radius: 7px; color: var(--aima-text-muted); background: #fafbfc; font-size: 10px; }\n.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-weight: 600; }\n.technical-details dl { margin-top: 10px; }\n.technical-list { display: grid; gap: 4px; margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--aima-border); }\n.technical-list strong { color: var(--aima-text-secondary); font-size: 10px; }\n.technical-list span { overflow-wrap: anywhere; color: var(--aima-text-muted); font-size: 9px; line-height: 15px; }\ndl {",
    'technical details style',
)

detail_path.write_text(detail, encoding='utf-8')

runtime_test_path = Path('frontend/tests/collection-runtime-design.spec.ts')
runtime_test = runtime_test_path.read_text(encoding='utf-8')
runtime_test = replace_once(
    runtime_test,
    """  it('辅助补采产品与可访问文案不绑定具体 Provider 或后台实现名', async () => {""",
    """  it('任务中心失败导入深链会定位到对应导入任务，而不是只打开运行中心首页', async () => {\n    const pageSource = await readCollectionRuntimeSource('CollectionRuntimePage.vue')\n    const taskCenterSource = await readFile(\n      new URL('../src/features/task-center/store.ts', import.meta.url),\n      'utf8',\n    )\n\n    expect(taskCenterSource).toContain('/collection-runtime?data_import_campaign_id=')\n    expect(taskCenterSource).toContain("actionLabel: hasImportFailure ? '处理失败项' : '查看'")\n    expect(pageSource).toContain('route.query.data_import_campaign_id')\n    expect(pageSource).toContain('await store.refreshHistoricalCampaign(campaignId)')\n    expect(pageSource).toContain('指定导入任务暂不可打开，请从列表重新选择。')\n  })\n\n  it('辅助补采产品与可访问文案不绑定具体 Provider 或后台实现名', async () => {""",
    'collection runtime deep-link regression',
)
runtime_test_path.write_text(runtime_test, encoding='utf-8')

frontend_audit_path = Path('frontend/tests/frontend-audit-regressions.spec.ts')
frontend_audit = frontend_audit_path.read_text(encoding='utf-8')
frontend_audit = replace_once(
    frontend_audit,
    """  it('offers a retry control when the shared vehicle catalog fails to load', async () => {""",
    """  it('keeps声音详情的工程身份和原始状态码下沉到技术详情', async () => {\n    const source = await readFile(\n      new URL('../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue', import.meta.url),\n      'utf8',\n    )\n    const technicalIndex = source.indexOf('<summary>技术详情</summary>')\n\n    expect(technicalIndex).toBeGreaterThan(-1)\n    expect(source).not.toContain('Content ID: {{ item.id }}')\n    expect(source.indexOf('<dt>Content ID</dt>')).toBeGreaterThan(technicalIndex)\n    expect(source.indexOf('<dt>外部内容 ID</dt>')).toBeGreaterThan(technicalIndex)\n    expect(source).toContain('<h4>内容可用状态</h4>')\n    expect(source).not.toContain('{{ item.availability.status }} · {{ item.availability.reason_code }} · {{ item.availability.evidence_kind }}')\n    expect(source).toContain("sourceLabel(item.source.provider_name)")\n    expect(source).toContain("contentTypeLabel(item.content_type)")\n  })\n\n  it('offers a retry control when the shared vehicle catalog fails to load', async () => {""",
    'content detail productization regression',
)
frontend_audit_path.write_text(frontend_audit, encoding='utf-8')
