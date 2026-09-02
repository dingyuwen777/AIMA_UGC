"""一次性完成 CHG-314 的 Admin 状态隔离与 Browser Mock 接线。

最终 Green 后必须与其它临时 Change 脚本、Workflow 一并删除。
"""

from __future__ import annotations

from pathlib import Path

from apply_chg314 import ROOT, replace_once


def patch_admin_page() -> None:
    path = "frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue"
    replace_once(
        path,
        '''const tab = ref<Tab>('vehicles')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const vehicles = ref<VehicleModelResponse[]>([])
const packs = ref<KeywordPackSummaryResponse[]>([])
const schemes = ref<AnalysisSchemeResponse[]>([])
const auditEvents = ref<AuditEventResponse[]>([])
const selectedPackId = ref('')
const linkedVehicleIds = ref<string[]>([])
const selectedSchemeVersionId = ref('')
''',
        '''const tab = ref<Tab>('vehicles')
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const vehicles = ref<VehicleModelResponse[]>([])
const packs = ref<KeywordPackSummaryResponse[]>([])
const schemes = ref<AnalysisSchemeResponse[]>([])
const auditEvents = ref<AuditEventResponse[]>([])
const selectedPackId = ref('')
const linkedVehicleIds = ref<string[]>([])
const selectedSchemeVersionId = ref('')
const vehicleLoading = ref(false)
const packLoading = ref(false)
const schemeLoading = ref(false)
const auditLoading = ref(false)
const vehicleError = ref<string | null>(null)
const packError = ref<string | null>(null)
const schemeError = ref<string | null>(null)
const auditError = ref<string | null>(null)
const auditTotal = ref(0)
const auditOffset = ref(0)
const auditLimit = 100
''',
    )
    replace_once(
        path,
        '''const vehicleFormValid = computed(() => Boolean(
  vehicleDraft.code.trim() && vehicleDraft.displayName.trim(),
))
const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
''',
        '''const vehicleFormValid = computed(() => Boolean(
  vehicleDraft.code.trim() && vehicleDraft.displayName.trim(),
))
const loading = computed(() => {
  if (tab.value === 'vehicles') return vehicleLoading.value
  if (tab.value === 'links') return vehicleLoading.value || packLoading.value
  if (tab.value === 'scheme') return schemeLoading.value
  return auditLoading.value
})
const activeResourceError = computed(() => {
  if (tab.value === 'vehicles') return vehicleError.value
  if (tab.value === 'links') return packError.value ?? vehicleError.value
  if (tab.value === 'scheme') return schemeError.value
  return auditError.value
})
const selectedPack = computed(() => packs.value.find((item) => item.id === selectedPackId.value) ?? null)
''',
    )
    replace_once(
        path,
        '''onMounted(refreshAll)

async function refreshAll(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [vehicleResponse, packResponse, schemeResponse, auditResponse] = await Promise.all([
      fetchVehicles(),
      fetchKeywordPacksForAdmin(),
      fetchSchemes(),
      fetchAuditEvents(),
    ])
    vehicles.value = vehicleResponse.items
    packs.value = packResponse.items
    schemes.value = schemeResponse.items
    auditEvents.value = auditResponse.items
    if (!selectedPackId.value && packs.value[0]) selectPack(packs.value[0].id)
    if (!selectedSchemeVersionId.value) {
      const initial = schemes.value.flatMap((item) => item.versions).find((item) => item.status === 'draft')
        ?? schemes.value.flatMap((item) => item.versions)[0]
      if (initial) selectSchemeVersion(initial.id)
    }
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}
''',
        '''onMounted(refreshAll)

/** 独立读取车型目录；单个资源失败不能拖垮其他管理员配置。 */
async function loadVehicles(): Promise<void> {
  vehicleLoading.value = true
  vehicleError.value = null
  try {
    vehicles.value = (await fetchVehicles()).items
    if (selectedPackId.value) selectPack(selectedPackId.value)
  } catch (reason) {
    vehicleError.value = apiErrorMessage(reason)
  } finally {
    vehicleLoading.value = false
  }
}

/** 独立读取词包目录，并在目录变化后重新校准当前选择。 */
async function loadPacks(): Promise<void> {
  packLoading.value = true
  packError.value = null
  try {
    packs.value = (await fetchKeywordPacksForAdmin()).items
    if (!packs.value.some((item) => item.id === selectedPackId.value)) {
      selectedPackId.value = packs.value[0]?.id ?? ''
    }
    if (selectedPackId.value) selectPack(selectedPackId.value)
  } catch (reason) {
    packError.value = apiErrorMessage(reason)
  } finally {
    packLoading.value = false
  }
}

/** 独立读取 Analysis Scheme，失败时保留其它管理员资源。 */
async function loadSchemes(): Promise<void> {
  schemeLoading.value = true
  schemeError.value = null
  try {
    schemes.value = (await fetchSchemes()).items
    const knownVersion = schemes.value
      .flatMap((item) => item.versions)
      .some((item) => item.id === selectedSchemeVersionId.value)
    if (!knownVersion) {
      const initial = schemes.value.flatMap((item) => item.versions).find((item) => item.status === 'draft')
        ?? schemes.value.flatMap((item) => item.versions)[0]
      selectedSchemeVersionId.value = initial?.id ?? ''
      if (initial) selectSchemeVersion(initial.id)
    }
  } catch (reason) {
    schemeError.value = apiErrorMessage(reason)
  } finally {
    schemeLoading.value = false
  }
}

/** 按后端 offset/limit/total Contract 读取当前审计页。 */
async function loadAudit(): Promise<void> {
  auditLoading.value = true
  auditError.value = null
  try {
    const response = await fetchAuditEvents(auditOffset.value, auditLimit)
    auditEvents.value = response.items
    auditTotal.value = response.total
    if (auditOffset.value >= response.total && auditOffset.value > 0) {
      auditOffset.value = Math.max(0, Math.floor(Math.max(0, response.total - 1) / auditLimit) * auditLimit)
      const corrected = await fetchAuditEvents(auditOffset.value, auditLimit)
      auditEvents.value = corrected.items
      auditTotal.value = corrected.total
    }
  } catch (reason) {
    auditError.value = apiErrorMessage(reason)
  } finally {
    auditLoading.value = false
  }
}

/** 并发恢复所有资源，但每个 Loader 自己拥有错误边界。 */
async function refreshAll(): Promise<void> {
  await Promise.all([loadVehicles(), loadPacks(), loadSchemes(), loadAudit()])
}

/** 只重试当前 Tab 依赖的资源，避免一个接口错误触发无关全页刷新。 */
async function retryActiveResource(): Promise<void> {
  if (tab.value === 'vehicles') return loadVehicles()
  if (tab.value === 'links') {
    await Promise.all([loadVehicles(), loadPacks()])
    return
  }
  if (tab.value === 'scheme') return loadSchemes()
  await loadAudit()
}

async function previousAuditPage(): Promise<void> {
  auditOffset.value = Math.max(0, auditOffset.value - auditLimit)
  await loadAudit()
}

async function nextAuditPage(): Promise<void> {
  if (auditOffset.value + auditLimit >= auditTotal.value) return
  auditOffset.value += auditLimit
  await loadAudit()
}
''',
    )
    replace_once(
        path,
        '''      </nav>

      <section
        v-if="loading"
''',
        '''      </nav>

      <AimaFeedbackBanner
        v-if="activeResourceError"
        tone="error"
        role="alert"
      >
        <strong>当前数据加载失败</strong>
        <span>{{ activeResourceError }}</span>
        <button
          class="retry-link"
          type="button"
          :disabled="loading"
          @click="retryActiveResource"
        >
          {{ loading ? '重试中…' : '重试当前数据' }}
        </button>
      </AimaFeedbackBanner>

      <section
        v-if="loading"
''',
    )
    replace_once(
        path,
        '''        <header>
          <div><h2>审计记录</h2><p>发布、回滚、车型与配置修改的安全摘要；不记录 Secret 和 Prompt 正文。</p></div><AimaButton
            size="small"
            @click="refreshAll"
          >
            刷新
          </AimaButton>
        </header><table>
''',
        '''        <header>
          <div><h2>审计记录</h2><p>发布、回滚、车型与配置修改的安全摘要；不记录 Secret 和 Prompt 正文。共 {{ auditTotal }} 条。</p></div><AimaButton
            size="small"
            :disabled="auditLoading"
            @click="loadAudit"
          >
            刷新
          </AimaButton>
        </header><table>
''',
    )
    replace_once(
        path,
        '''          </tbody>
        </table>
      </section>
''',
        '''          </tbody>
        </table>
        <nav
          v-if="auditTotal > 0"
          class="audit-pagination"
          aria-label="审计记录分页"
        >
          <span>第 {{ Math.floor(auditOffset / auditLimit) + 1 }} / {{ Math.ceil(auditTotal / auditLimit) }} 页 · 共 {{ auditTotal }} 条</span>
          <div>
            <AimaButton
              size="small"
              :disabled="auditLoading || auditOffset === 0"
              @click="previousAuditPage"
            >
              上一页
            </AimaButton>
            <AimaButton
              size="small"
              :disabled="auditLoading || auditOffset + auditLimit >= auditTotal"
              @click="nextAuditPage"
            >
              下一页
            </AimaButton>
          </div>
        </nav>
      </section>
''',
    )
    replace_once(
        path,
        '''.audit-card { overflow: auto; }
.audit-card code { display: block; max-width: 360px; overflow-wrap: anywhere; white-space: normal; font-size: 9px; }
''',
        '''.retry-link { width: max-content; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
.retry-link:disabled { cursor: wait; opacity: .6; }
.audit-card { overflow: auto; }
.audit-card code { display: block; max-width: 360px; overflow-wrap: anywhere; white-space: normal; font-size: 9px; }
.audit-pagination { display: flex; min-height: 48px; align-items: center; justify-content: space-between; gap: 16px; padding-top: 10px; color: var(--aima-text-muted); font-size: 11px; }
.audit-pagination > div { display: flex; gap: 8px; }
''',
    )


def patch_browser_mock_imports() -> None:
    e2e = ROOT / "frontend/e2e"
    changed = 0
    for target in sorted(e2e.glob("*.spec.ts")):
        text = target.read_text(encoding="utf-8")
        if "from '@playwright/test'" not in text:
            continue
        target.write_text(text.replace("from '@playwright/test'", "from './fixture'"), encoding="utf-8")
        changed += 1
    if changed < 10:
        raise RuntimeError(f"expected at least 10 Browser Mock specs to migrate, got {changed}")


def patch_historical_retry_blackbox() -> None:
    path = "frontend/e2e/historical-migration.spec.ts"
    replace_once(
        path,
        '''    status: 'partial_failed',
    can_start: false,
    stats: { ...readyCampaign.stats, created: 60, failed: 60 },
''',
        '''    status: 'partial_failed',
    can_start: false,
    failed_chunk_count: 1,
    stats: { ...readyCampaign.stats, created: 60, failed: 60 },
''',
    )
    old_items = '''      body: JSON.stringify({
        items: [{
          id: '41111111-2222-4333-8444-555555555555',
          parent_item_id: '51111111-2222-4333-8444-555555555555',
          item_kind: 'chunk',
          relative_path: '2025-archive/part-001.xlsx',
          ordinal: 0,
          artifact_id: '61111111-2222-4333-8444-555555555555',
          sha256: 'a'.repeat(64),
          row_start: 1,
          row_end: 60,
          row_count: 60,
          status: 'failed',
          attempt_count: 1,
          stats: {},
          error_code: 'historical_chunk_failed',
          created_at: '2026-08-26T10:00:00+08:00',
          started_at: '2026-08-26T10:01:00+08:00',
          finished_at: '2026-08-26T10:02:00+08:00',
        }],
      }),
'''
    new_items = '''      body: JSON.stringify({
        items: [],
        total_count: 201,
        has_more: true,
      }),
'''
    replace_once(path, old_items, new_items)
    replace_once(
        path,
        "test('shows failed chunks and submits an explicit retry action'",
        "test('uses campaign failed-chunk facts even when bounded detail omits failed chunks'",
    )


def widen_fixture_type_exports() -> None:
    path = "frontend/e2e/fixture.ts"
    replace_once(
        path,
        "export type { Locator, Page, Request, Response, Route } from '@playwright/test'\n",
        "export type * from '@playwright/test'\n",
    )


def main() -> None:
    patch_admin_page()
    patch_browser_mock_imports()
    patch_historical_retry_blackbox()
    widen_fixture_type_exports()


if __name__ == "__main__":
    main()
