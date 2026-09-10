import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  BrandResponse,
  CollectionCapabilitiesResponse,
  CollectionPlanCreateRequest,
  CollectionPlanResponse,
  CollectionPlanUpdateRequest,
  CollectionPlatform,
  KeywordPackItemUpdateRequest,
  KeywordPackKeywordCreateRequest,
  KeywordPackUpdateRequest,
  KeywordPackResponse,
  KeywordPackSummaryResponse,
  ResourceLifecycleResponse,
} from '../../generated/api/client'
import {
  CollectionStrategyApiError,
  addPackKeyword,
  archivePack,
  archivePlan,
  copyPack,
  copyPlan,
  createPack,
  createPlan,
  deletePack,
  deletePlan,
  fetchArchivedPacks,
  fetchArchivedPlans,
  fetchBrands,
  fetchCapabilities,
  fetchKeywordPacks,
  fetchPack,
  fetchPackDeleteEligibility,
  fetchPlanDeleteEligibility,
  fetchPlans,
  removePackKeyword,
  restorePack,
  restorePlan,
  setPackEnabled,
  setPlanEnabled,
  updatePack,
  updatePackKeyword,
  updatePlan,
} from './api'
import { planExecutionReason } from './eligibility'

export type StrategyTab = 'keywords' | 'plans'

interface PlanFilters {
  search: string
  enabled: '' | 'true' | 'false'
  platform: '' | CollectionPlatform
}

function errorMessage(error: unknown): string {
  if (error instanceof CollectionStrategyApiError) return error.message
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

export const useCollectionStrategyStore = defineStore('collection-strategy', () => {
  const activeTab = ref<StrategyTab>('plans')
  const packs = ref<KeywordPackSummaryResponse[]>([])
  const packCatalog = ref<KeywordPackSummaryResponse[]>([])
  const archivedPacks = ref<ResourceLifecycleResponse[]>([])
  const brandCatalog = ref<BrandResponse[]>([])
  const packTotal = ref(0)
  const packOffset = ref(0)
  const packLimit = 20
  const capabilities = ref<CollectionCapabilitiesResponse | null>(null)
  const plans = ref<CollectionPlanResponse[]>([])
  const archivedPlans = ref<ResourceLifecycleResponse[]>([])
  const planTotal = ref(0)
  const enabledPlanCount = ref(0)
  const planOffset = ref(0)
  const planLimit = 20
  const selectedPack = ref<KeywordPackResponse | null>(null)
  const selectedPlan = ref<CollectionPlanResponse | null>(null)
  const packDetails = ref<Record<string, KeywordPackResponse>>({})
  const enabledPlanPackIds = ref<string[]>([])
  const loadingPackDetails = ref(false)
  const loadingArchived = ref(false)
  const filters = reactive<PlanFilters>({ search: '', enabled: '', platform: '' })
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  let refreshVersion = 0
  let packSelectionVersion = 0
  let pendingPackDetails = 0

  const enabledPacks = computed(() =>
    packCatalog.value.filter((pack) => pack.enabled && pack.keyword_count > 0),
  )
  const enabledBrandCount = computed(() =>
    brandCatalog.value.filter((brand) => brand.status === 'active').length,
  )

  /** 分页读取完整词包摘要目录，供跨页配置引用，不能用当前列表页冒充全集。 */
  async function fetchAllKeywordPacks(): Promise<KeywordPackSummaryResponse[]> {
    const result: KeywordPackSummaryResponse[] = []
    let offset = 0
    while (true) {
      const page = await fetchKeywordPacks({ offset, limit: 100 })
      result.push(...page.items)
      offset += page.items.length
      if (offset >= page.total || page.items.length === 0) return result
    }
  }

  /** 分页读取完整品牌目录，供已停用品牌的历史计划继续显示真实名称。 */
  async function fetchAllBrands(): Promise<BrandResponse[]> {
    const result: BrandResponse[] = []
    let offset = 0
    while (true) {
      const page = await fetchBrands({ offset, limit: 200 })
      result.push(...page.items)
      offset += page.items.length
      if (offset >= page.total || page.items.length === 0) return result
    }
  }

  async function fetchAllEnabledPlans(): Promise<CollectionPlanResponse[]> {
    const result: CollectionPlanResponse[] = []
    let offset = 0
    while (true) {
      const page = await fetchPlans({ enabled: true, offset, limit: 100 })
      result.push(...page.items)
      offset += page.items.length
      if (offset >= page.total || page.items.length === 0) return result
    }
  }

  async function loadPackDetails(packIds: readonly string[]): Promise<void> {
    const version = refreshVersion
    const missing = [...new Set(packIds)].filter((id) => !packDetails.value[id])
    if (missing.length === 0) return
    pendingPackDetails += 1
    loadingPackDetails.value = true
    try {
      const loaded = await Promise.all(missing.map((id) => fetchPack(id)))
      if (version !== refreshVersion) return
      packDetails.value = {
        ...packDetails.value,
        ...Object.fromEntries(loaded.filter((pack) =>
          !packDetails.value[pack.id] || packDetails.value[pack.id]!.version <= pack.version,
        ).map((pack) => [pack.id, pack])),
      }
    } finally {
      if (version === refreshVersion) {
        pendingPackDetails -= 1
        loadingPackDetails.value = pendingPackDetails > 0
      }
    }
  }

  /** 并行恢复策略工作区事实，并保持列表分页与跨页引用目录各自独立。 */
  async function refresh(): Promise<void> {
    const version = ++refreshVersion
    pendingPackDetails = 0
    loadingPackDetails.value = false
    const selectionVersion = packSelectionVersion
    loading.value = true
    error.value = null
    try {
      const [packPage, allPacks, allBrands, providerCapabilities, planPage, enabledPlans] = await Promise.all([
        fetchKeywordPacks({ offset: packOffset.value, limit: packLimit }),
        fetchAllKeywordPacks(),
        fetchAllBrands(),
        fetchCapabilities(),
        fetchPlans({
          search: filters.search.trim() || undefined,
          enabled: filters.enabled ? filters.enabled === 'true' : undefined,
          platform: filters.platform || undefined,
          offset: planOffset.value,
          limit: planLimit,
        }),
        fetchAllEnabledPlans(),
      ])
      if (version !== refreshVersion) return
      packs.value = packPage.items
      packCatalog.value = allPacks
      brandCatalog.value = allBrands
      packTotal.value = packPage.total
      capabilities.value = providerCapabilities
      plans.value = planPage.items
      planTotal.value = planPage.total
      enabledPlanCount.value = planPage.enabled_count
      enabledPlanPackIds.value = [...new Set(enabledPlans.flatMap((plan) => plan.keyword_pack_ids))]
      packDetails.value = {}
      await loadPackDetails(planPage.items.flatMap((plan) => plan.keyword_pack_ids))
      if (version !== refreshVersion) return
      const selectedId = allPacks.some((pack) => pack.id === selectedPack.value?.id)
        ? selectedPack.value?.id
        : packPage.items[0]?.id
      if (selectedId && selectionVersion === packSelectionVersion) {
        const detail = packDetails.value[selectedId] ?? await fetchPack(selectedId)
        if (version !== refreshVersion || selectionVersion !== packSelectionVersion) return
        selectedPack.value = detail
        packDetails.value = { ...packDetails.value, [detail.id]: detail }
      } else if (selectionVersion === packSelectionVersion) {
        selectedPack.value = null
      }
      if (selectedPlan.value) {
        selectedPlan.value = planPage.items.find((plan) => plan.id === selectedPlan.value?.id) ?? null
      }
    } catch (reason) {
      if (version === refreshVersion) error.value = errorMessage(reason)
    } finally {
      if (version === refreshVersion) loading.value = false
    }
  }

  async function openPack(packId: string): Promise<void> {
    const version = ++packSelectionVersion
    error.value = null
    try {
      const pack = await fetchPack(packId)
      if (version !== packSelectionVersion) return
      selectedPack.value = pack
      packDetails.value = { ...packDetails.value, [pack.id]: pack }
    } catch (reason) {
      if (version === packSelectionVersion) error.value = errorMessage(reason)
    }
  }

  async function savePack(name: string, description: string, keywords: KeywordPackKeywordCreateRequest[]): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const created = await createPack({
        name,
        description,
        keywords,
      })
      selectedPack.value = created
      packDetails.value = { ...packDetails.value, [created.id]: created }
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function savePackChanges(packId: string, request: KeywordPackUpdateRequest): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const updated = await updatePack(packId, request)
      selectedPack.value = updated
      packDetails.value = { ...packDetails.value, [updated.id]: updated }
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function addKeyword(packId: string, text: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const updated = await addPackKeyword(packId, { text, priority: 100, enabled: true })
      selectedPack.value = updated
      packDetails.value = { ...packDetails.value, [updated.id]: updated }
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function updateKeyword(
    keywordId: string,
    request: Omit<KeywordPackItemUpdateRequest, 'expected_version'>,
  ): Promise<boolean> {
    const pack = selectedPack.value
    if (!pack) return false
    saving.value = true
    error.value = null
    try {
      const updated = await updatePackKeyword(pack.id, keywordId, {
        ...request,
        expected_version: pack.version,
      })
      selectedPack.value = updated
      packDetails.value = { ...packDetails.value, [updated.id]: updated }
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function removeKeyword(keywordId: string, platformScope: string): Promise<boolean> {
    const pack = selectedPack.value
    if (!pack) return false
    saving.value = true
    error.value = null
    try {
      const updated = await removePackKeyword(pack.id, keywordId, {
        expected_version: pack.version,
        platform_scope: platformScope as KeywordPackItemUpdateRequest['platform_scope'],
      })
      selectedPack.value = updated
      packDetails.value = { ...packDetails.value, [updated.id]: updated }
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  /** 启用计划仍引用词包时阻止停用，避免下一次搜索失去冻结来源。 */
  function packToggleReason(pack: KeywordPackSummaryResponse): string | null {
    if (!pack.enabled) return null
    if (enabledPlanPackIds.value.includes(pack.id)) return '启用中的采集计划正在引用该词包。'
    return null
  }

  async function togglePack(pack: KeywordPackSummaryResponse): Promise<void> {
    const reason = packToggleReason(pack)
    if (reason) {
      error.value = reason
      return
    }
    saving.value = true
    error.value = null
    try {
      await setPackEnabled(pack.id, !pack.enabled)
      await refresh()
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      saving.value = false
    }
  }

  async function copySelectedPack(name: string): Promise<boolean> {
    const pack = selectedPack.value
    if (!pack) return false
    saving.value = true
    error.value = null
    try {
      const copied = await copyPack(pack.id, { name: name.trim() })
      packOffset.value = 0
      await refresh()
      await openPack(copied.id)
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function archiveSelectedPack(): Promise<boolean> {
    const pack = selectedPack.value
    if (!pack) return false
    saving.value = true
    error.value = null
    try {
      await archivePack(pack.id)
      selectedPack.value = null
      await Promise.all([refresh(), loadArchivedPacks()])
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function loadArchivedPacks(): Promise<void> {
    loadingArchived.value = true
    error.value = null
    try {
      archivedPacks.value = (await fetchArchivedPacks()).items
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingArchived.value = false
    }
  }

  async function restoreArchivedPack(packId: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const restored = await restorePack(packId)
      await Promise.all([refresh(), loadArchivedPacks()])
      await openPack(restored.id)
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function deleteArchivedPack(packId: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const eligibility = await fetchPackDeleteEligibility(packId)
      if (!eligibility.eligible) {
        error.value = (eligibility.blocking_reasons ?? []).join('；') || '该词包已有业务引用，只能保留归档记录。'
        return false
      }
      await deletePack(packId)
      await loadArchivedPacks()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  function planReason(request: CollectionPlanCreateRequest): string | null {
    return planExecutionReason({
      keywordPackIds: request.keyword_pack_ids ?? [],
      platforms: request.platforms,
      packDetails: packDetails.value,
      capabilities: capabilities.value,
    })
  }

  async function savePlan(request: CollectionPlanCreateRequest): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      await loadPackDetails(request.keyword_pack_ids ?? [])
      const reason = planReason(request)
      if (reason) {
        error.value = reason
        return false
      }
      selectedPlan.value = await createPlan(request)
      planOffset.value = 0
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function updateExistingPlan(request: CollectionPlanUpdateRequest): Promise<boolean> {
    const plan = selectedPlan.value
    if (!plan) return false
    saving.value = true
    error.value = null
    try {
      await loadPackDetails(request.keyword_pack_ids ?? [])
      const reason = planReason(request)
      if (reason) {
        error.value = reason
        return false
      }
      selectedPlan.value = await updatePlan(plan.id, request)
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function openPlan(planId: string): Promise<void> {
    error.value = null
    selectedPlan.value = plans.value.find((plan) => plan.id === planId) ?? null
  }

  function planToggleReason(plan: CollectionPlanResponse): string | null {
    if (plan.enabled) return null
    return planExecutionReason({
      keywordPackIds: plan.keyword_pack_ids ?? [],
      platforms: plan.platforms,
      packDetails: packDetails.value,
      capabilities: capabilities.value,
    })
  }

  async function togglePlan(plan: CollectionPlanResponse): Promise<void> {
    if (!plan.enabled) {
      try {
        await loadPackDetails(plan.keyword_pack_ids ?? [])
      } catch (reason) {
        error.value = errorMessage(reason)
        return
      }
      const reason = planToggleReason(plan)
      if (reason) {
        error.value = reason
        return
      }
    }
    saving.value = true
    error.value = null
    try {
      await setPlanEnabled(plan.id, !plan.enabled)
      await refresh()
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      saving.value = false
    }
  }

  async function copySelectedPlan(name: string): Promise<boolean> {
    const plan = selectedPlan.value
    if (!plan) return false
    saving.value = true
    error.value = null
    try {
      const copied = await copyPlan(plan.id, { name: name.trim() })
      planOffset.value = 0
      await refresh()
      selectedPlan.value = copied
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function archiveSelectedPlan(): Promise<boolean> {
    const plan = selectedPlan.value
    if (!plan) return false
    saving.value = true
    error.value = null
    try {
      await archivePlan(plan.id)
      selectedPlan.value = null
      await Promise.all([refresh(), loadArchivedPlans()])
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function loadArchivedPlans(): Promise<void> {
    loadingArchived.value = true
    error.value = null
    try {
      archivedPlans.value = (await fetchArchivedPlans()).items
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loadingArchived.value = false
    }
  }

  async function restoreArchivedPlan(planId: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const restored = await restorePlan(planId)
      await Promise.all([refresh(), loadArchivedPlans()])
      selectedPlan.value = restored
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function deleteArchivedPlan(planId: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const eligibility = await fetchPlanDeleteEligibility(planId)
      if (!eligibility.eligible) {
        error.value = (eligibility.blocking_reasons ?? []).join('；') || '该采集计划已有历史记录，只能保留归档记录。'
        return false
      }
      await deletePlan(planId)
      await loadArchivedPlans()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  function resetPlanFilters(): void {
    filters.search = ''
    filters.enabled = ''
    filters.platform = ''
    planOffset.value = 0
  }

  async function firstPlanPage(): Promise<void> {
    planOffset.value = 0
    await refresh()
  }

  async function previousPlanPage(): Promise<void> {
    planOffset.value = Math.max(0, planOffset.value - planLimit)
    await refresh()
  }

  async function nextPlanPage(): Promise<void> {
    if (planOffset.value + planLimit >= planTotal.value) return
    planOffset.value += planLimit
    await refresh()
  }

  /** 仅刷新关键词包当前页，避免翻页时重复拉取无关的计划和 Capability。 */
  async function loadPackPage(): Promise<void> {
    const version = ++refreshVersion
    const selectionVersion = ++packSelectionVersion
    pendingPackDetails = 0
    loadingPackDetails.value = false
    loading.value = true
    error.value = null
    try {
      const page = await fetchKeywordPacks({ offset: packOffset.value, limit: packLimit })
      if (version !== refreshVersion) return
      packs.value = page.items
      packTotal.value = page.total
      const first = page.items[0]
      if (selectionVersion === packSelectionVersion) {
        if (first) {
          const detail = await fetchPack(first.id)
          if (version !== refreshVersion || selectionVersion !== packSelectionVersion) return
          selectedPack.value = detail
          packDetails.value = { ...packDetails.value, [detail.id]: detail }
        } else selectedPack.value = null
      }
    } catch (reason) {
      if (version === refreshVersion) error.value = errorMessage(reason)
    } finally {
      if (version === refreshVersion) loading.value = false
    }
  }

  /** 返回关键词包上一页，并保持页码不小于零。 */
  async function previousPackPage(): Promise<void> {
    packOffset.value = Math.max(0, packOffset.value - packLimit)
    await loadPackPage()
  }

  /** 在后端 total 仍有下一页时推进关键词包分页。 */
  async function nextPackPage(): Promise<void> {
    if (packOffset.value + packLimit >= packTotal.value) return
    packOffset.value += packLimit
    await loadPackPage()
  }

  return {
    activeTab,
    packs,
    packCatalog,
    archivedPacks,
    brandCatalog,
    packTotal,
    packOffset,
    packLimit,
    enabledPacks,
    enabledBrandCount,
    capabilities,
    plans,
    archivedPlans,
    planTotal,
    enabledPlanCount,
    planOffset,
    planLimit,
    selectedPack,
    selectedPlan,
    packDetails,
    loadingPackDetails,
    loadingArchived,
    filters,
    loading,
    saving,
    error,
    refresh,
    openPack,
    savePack,
    savePackChanges,
    addKeyword,
    updateKeyword,
    removeKeyword,
    packToggleReason,
    togglePack,
    copySelectedPack,
    archiveSelectedPack,
    loadArchivedPacks,
    restoreArchivedPack,
    deleteArchivedPack,
    loadPackDetails,
    planReason,
    savePlan,
    updateExistingPlan,
    openPlan,
    planToggleReason,
    togglePlan,
    copySelectedPlan,
    archiveSelectedPlan,
    loadArchivedPlans,
    restoreArchivedPlan,
    deleteArchivedPlan,
    resetPlanFilters,
    firstPlanPage,
    previousPlanPage,
    nextPlanPage,
    previousPackPage,
    nextPackPage,
  }
})
