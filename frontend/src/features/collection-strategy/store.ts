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
} from '../../generated/api/client'
import {
  addPackKeyword,
  CollectionStrategyApiError,
  createPack,
  createPlan,
  fetchCapabilities,
  fetchGlobalRelevance,
  fetchPack,
  fetchPlans,
  fetchKeywordPacks,
  setGlobalRelevance,
  setPackEnabled,
  setPlanEnabled,
} from './api'

export type StrategyTab = 'keywords' | 'relevance' | 'plans'

interface PlanFilters {
  search: string
  enabled: '' | 'true' | 'false'
  platform: '' | CollectionPlatform
}

function errorMessage(reason: unknown): string {
  if (reason instanceof CollectionStrategyApiError) {
    return `${reason.message}（request_id: ${reason.requestId}）`
  }
  if (reason instanceof Error && reason.message) return reason.message
  return '请求失败，请稍后重试。'
}

export const useCollectionStrategyStore = defineStore('collection-strategy', () => {
  const activeTab = ref<StrategyTab>('plans')
  const packs = ref<KeywordPackSummaryResponse[]>([])
  const packTotal = ref(0)
  const relevance = ref<GlobalRelevanceConfigResponse | null>(null)
  const capabilities = ref<CollectionCapabilitiesResponse | null>(null)
  const plans = ref<CollectionPlanResponse[]>([])
  const planTotal = ref(0)
  const enabledPlanCount = ref(0)
  const planOffset = ref(0)
  const planLimit = 20
  const selectedPack = ref<KeywordPackResponse | null>(null)
  const selectedPlan = ref<CollectionPlanResponse | null>(null)
  const filters = reactive<PlanFilters>({ search: '', enabled: '', platform: '' })
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  const enabledPacks = computed(() =>
    packs.value.filter((pack) => pack.enabled && pack.keyword_count > 0),
  )

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const relevancePromise = fetchGlobalRelevance().catch((reason: unknown) => {
        if (reason instanceof CollectionStrategyApiError && reason.status === 409) return null
        throw reason
      })
      const [packPage, currentRelevance, providerCapabilities, planPage] = await Promise.all([
        fetchKeywordPacks({ offset: 0, limit: 100 }),
        relevancePromise,
        fetchCapabilities(),
        fetchPlans({
          search: filters.search.trim() || undefined,
          enabled: filters.enabled ? filters.enabled === 'true' : undefined,
          platform: filters.platform || undefined,
          offset: planOffset.value,
          limit: planLimit,
        }),
      ])
      packs.value = packPage.items
      packTotal.value = packPage.total
      relevance.value = currentRelevance
      capabilities.value = providerCapabilities
      plans.value = planPage.items
      planTotal.value = planPage.total
      enabledPlanCount.value = planPage.enabled_count
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
    }
  }

  async function openPack(packId: string): Promise<void> {
    error.value = null
    try {
      selectedPack.value = await fetchPack(packId)
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
      selectedPack.value = await addPackKeyword(packId, { text, priority: 100, enabled: true })
      await refresh()
      return true
    } catch (reason) {
      error.value = errorMessage(reason)
      return false
    } finally {
      saving.value = false
    }
  }

  async function togglePack(pack: KeywordPackSummaryResponse): Promise<void> {
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

  async function savePlan(request: CollectionPlanCreateRequest): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
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
    try {
      selectedPlan.value = plans.value.find((plan) => plan.id === planId) ?? null
      if (selectedPlan.value === null) return
    } catch (reason) {
      error.value = errorMessage(reason)
    }
  }

  async function togglePlan(plan: CollectionPlanResponse): Promise<void> {
    saving.value = true
    error.value = null
    try {
      selectedPlan.value = await setPlanEnabled(plan.id, !plan.enabled)
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
    if (planOffset.value === 0) return
    planOffset.value = Math.max(0, planOffset.value - planLimit)
    await refresh()
  }

  async function nextPlanPage(): Promise<void> {
    if (planOffset.value + planLimit >= planTotal.value) return
    planOffset.value += planLimit
    await refresh()
  }

  return {
    activeTab,
    packs,
    packTotal,
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
    filters,
    loading,
    saving,
    error,
    refresh,
    openPack,
    savePack,
    addKeyword,
    togglePack,
    saveRelevance,
    savePlan,
    openPlan,
    togglePlan,
    resetPlanFilters,
    firstPlanPage,
    previousPlanPage,
    nextPlanPage,
  }
})
