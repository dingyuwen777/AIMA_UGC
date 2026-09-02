import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import type {
  CollectionCapabilitiesResponse,
  CollectionPlanCreateRequest,
  CollectionPlanResponse,
  CollectionPlatform,
  GlobalRelevanceConfigResponse,
  KeywordPackResponse,
  KeywordPackSummaryResponse,
  VehicleModelResponse,
} from '../../generated/api/client'
import {
  CollectionStrategyApiError,
  addPackKeyword,
  createPack,
  createPlan,
  fetchCapabilities,
  fetchGlobalRelevance,
  fetchKeywordPacks,
  fetchPack,
  fetchPlans,
  fetchVehicleModels,
  setGlobalRelevance,
  setPackEnabled,
  setPlanEnabled,
} from './api'
import { planExecutionReason } from './eligibility'

export type StrategyTab = 'keywords' | 'relevance' | 'plans'

interface PlanFilters {
  search: string
  enabled: '' | 'true' | 'false'
  platform: '' | CollectionPlatform
}

function errorMessage(error: unknown): string {
  if (error instanceof CollectionStrategyApiError) {
    return `${error.message}（request_id: ${error.requestId}）`
  }
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请稍后重试。'
}

export const useCollectionStrategyStore = defineStore('collection-strategy', () => {
  const activeTab = ref<StrategyTab>('plans')
  const packs = ref<KeywordPackSummaryResponse[]>([])
  const packCatalog = ref<KeywordPackSummaryResponse[]>([])
  const vehicleCatalog = ref<VehicleModelResponse[]>([])
  const packTotal = ref(0)
  const packOffset = ref(0)
  const packLimit = 20
  const relevance = ref<GlobalRelevanceConfigResponse | null>(null)
  const capabilities = ref<CollectionCapabilitiesResponse | null>(null)
  const plans = ref<CollectionPlanResponse[]>([])
  const planTotal = ref(0)
  const enabledPlanCount = ref(0)
  const planOffset = ref(0)
  const planLimit = 20
  const selectedPack = ref<KeywordPackResponse | null>(null)
  const selectedPlan = ref<CollectionPlanResponse | null>(null)
  const packDetails = ref<Record<string, KeywordPackResponse>>({})
  const enabledPlanPackIds = ref<string[]>([])
  const loadingPackDetails = ref(false)
  const filters = reactive<PlanFilters>({ search: '', enabled: '', platform: '' })
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  const enabledPacks = computed(() =>
    packCatalog.value.filter((pack) => pack.enabled && pack.keyword_count > 0),
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

  /**
   * 分页读取完整车型目录供计划历史引用展示。
   * 不传 status，避免把 active-only 创建候选语义错误复用到 deprecated/merged 历史计划。
   */
  async function fetchAllVehicleModels(): Promise<VehicleModelResponse[]> {
    const result: VehicleModelResponse[] = []
    let offset = 0
    while (true) {
      const page = await fetchVehicleModels({ offset, limit: 200 })
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
    const missing = [...new Set(packIds)].filter((id) => !packDetails.value[id])
    if (missing.length === 0) return
    loadingPackDetails.value = true
    try {
      const loaded = await Promise.all(missing.map((id) => fetchPack(id)))
      packDetails.value = {
        ...packDetails.value,
        ...Object.fromEntries(loaded.map((pack) => [pack.id, pack])),
      }
    } finally {
      loadingPackDetails.value = false
    }
  }

  /** 并行恢复策略工作区事实，并保持列表分页与跨页引用目录各自独立。 */
  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const relevancePromise = fetchGlobalRelevance().catch((reason: unknown) => {
        if (reason instanceof CollectionStrategyApiError && reason.status === 409) return null
        throw reason
      })
      const [packPage, allPacks, allVehicles, currentRelevance, providerCapabilities, planPage, enabledPlans] = await Promise.all([
        fetchKeywordPacks({ offset: packOffset.value, limit: packLimit }),
        fetchAllKeywordPacks(),
        fetchAllVehicleModels(),
        relevancePromise,
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
      packs.value = packPage.items
      packCatalog.value = allPacks
      vehicleCatalog.value = allVehicles
      packTotal.value = packPage.total
      relevance.value = currentRelevance
      capabilities.value = providerCapabilities
      plans.value = planPage.items
      planTotal.value = planPage.total
      enabledPlanCount.value = planPage.enabled_count
      enabledPlanPackIds.value = [...new Set(enabledPlans.flatMap((plan) => plan.keyword_pack_ids))]
      packDetails.value = {}
      await loadPackDetails(planPage.items.flatMap((plan) => plan.keyword_pack_ids))
      const selectedId = allPacks.some((pack) => pack.id === selectedPack.value?.id)
        ? selectedPack.value?.id
        : packPage.items[0]?.id
      if (selectedId) {
        const detail = packDetails.value[selectedId] ?? await fetchPack(selectedId)
        selectedPack.value = detail
        packDetails.value = { ...packDetails.value, [detail.id]: detail }
      } else {
        selectedPack.value = null
      }
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
    }
  }

  async function openPack(packId: string): Promise<void> {
    error.value = null
    try {
      const pack = await fetchPack(packId)
      selectedPack.value = pack
      packDetails.value = { ...packDetails.value, [pack.id]: pack }
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function savePack(name: string, description: string, keywords: string[]): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      let created = await createPack({ name, description })
      for (const text of keywords) {
        created = await addPackKeyword(created.id, { text, priority: 100, enabled: true })
      }
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

  /** 根据全局相关性与启用计划引用判断词包是否允许停用。 */
  function packToggleReason(pack: KeywordPackSummaryResponse): string | null {
    if (!pack.enabled) return null
    if (relevance.value?.keyword_pack_id === pack.id) return '全局相关性正在引用该词包。'
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

  async function saveRelevance(packId: string): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      relevance.value = await setGlobalRelevance(packId)
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
      vehicleModelIds: request.vehicle_model_ids ?? [],
      platforms: request.platforms,
      requireRelevance: request.enabled ?? true,
      relevanceAvailable: relevance.value !== null,
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

  async function openPlan(planId: string): Promise<void> {
    error.value = null
    selectedPlan.value = plans.value.find((plan) => plan.id === planId) ?? null
  }

  function planToggleReason(plan: CollectionPlanResponse): string | null {
    if (plan.enabled) return null
    return planExecutionReason({
      keywordPackIds: plan.keyword_pack_ids ?? [],
      vehicleModelIds: plan.vehicle_model_ids ?? [],
      platforms: plan.platforms,
      requireRelevance: true,
      relevanceAvailable: relevance.value !== null,
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
    loading.value = true
    error.value = null
    try {
      const page = await fetchKeywordPacks({ offset: packOffset.value, limit: packLimit })
      packs.value = page.items
      packTotal.value = page.total
      const first = page.items[0]
      if (first) await openPack(first.id)
      else selectedPack.value = null
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
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
    vehicleCatalog,
    packTotal,
    packOffset,
    packLimit,
    enabledPacks,
    relevance,
    capabilities,
    plans,
    planTotal,
    enabledPlanCount,
    planOffset,
    planLimit,
    selectedPack,
    selectedPlan,
    packDetails,
    loadingPackDetails,
    filters,
    loading,
    saving,
    error,
    refresh,
    openPack,
    savePack,
    addKeyword,
    packToggleReason,
    togglePack,
    saveRelevance,
    loadPackDetails,
    planReason,
    savePlan,
    openPlan,
    planToggleReason,
    togglePlan,
    resetPlanFilters,
    firstPlanPage,
    previousPlanPage,
    nextPlanPage,
    previousPackPage,
    nextPackPage,
  }
})
