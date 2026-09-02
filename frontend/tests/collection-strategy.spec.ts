import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CollectionPlanResponse } from '../src/generated/api/client'

const generated = vi.hoisted(() => ({
  listKeywordPacks: vi.fn(),
  createKeywordPack: vi.fn(),
  getKeywordPack: vi.fn(),
  updateKeywordPackEnabled: vi.fn(),
  addKeywordToPack: vi.fn(),
  getGlobalRelevanceConfig: vi.fn(),
  setGlobalRelevanceConfig: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  listCollectionPlans: vi.fn(),
  createCollectionPlan: vi.fn(),
  getCollectionPlan: vi.fn(),
  updateCollectionPlanEnabled: vi.fn(),
  listVehicleModels: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import { createPlan, fetchKeywordPacks } from '../src/features/collection-strategy/api'
import { useCollectionStrategyStore } from '../src/features/collection-strategy/store'

const globalPack = {
  id: '11111111-1111-4111-8111-111111111111',
  name: '全局相关性词包',
  description: '',
  enabled: true,
  version: 1,
  keyword_count: 1,
}

const packDetail = {
  ...globalPack,
  keywords: [{
    id: '22222222-2222-4222-8222-222222222222',
    text: '爱玛',
    platform_scope: 'all',
    enabled: true,
    priority: 100,
    note: '',
  }],
}

const historicalVehicle = {
  id: '66666666-6666-4666-8666-666666666666',
  code: 'A7',
  display_name: '爱玛 A7',
  status: 'deprecated' as const,
  version: 3,
  catalog_version: 9,
  merged_into_id: null,
  aliases: [],
  keyword_pack_ids: [],
  referenced: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-28T00:00:00Z',
}

describe('collection strategy feature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    generated.listKeywordPacks.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 })
    generated.listCollectionPlans.mockResolvedValue({ items: [], total: 0, enabled_count: 0, offset: 0, limit: 20 })
    generated.listVehicleModels.mockResolvedValue({ items: [], total: 0, catalog_version: 1, offset: 0, limit: 200 })
    generated.getCollectionCapabilities.mockResolvedValue({ provider_configs: [], capabilities: [] })
    generated.getGlobalRelevanceConfig.mockResolvedValue({
      keyword_pack_id: 'pack-global', keyword_pack_version: 8, version: 3,
      effective_keywords: ['爱玛'], updated_at: '2026-08-21T00:00:00Z',
    })
    generated.getKeywordPack.mockResolvedValue(packDetail)
  })

  it('delegates keyword pack listing to the generated Orval client', async () => {
    await fetchKeywordPacks({ search: '爱玛', enabled: true, offset: 0, limit: 20 })
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ search: '爱玛', enabled: true, offset: 0, limit: 20 })
  })

  it('loads packs, vehicles, global relevance, capabilities, and plans as one workspace', async () => {
    const store = useCollectionStrategyStore()
    await store.refresh()
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 20 })
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 100 })
    expect(generated.listVehicleModels).toHaveBeenCalledWith({ offset: 0, limit: 200 })
    expect(generated.getGlobalRelevanceConfig).toHaveBeenCalledOnce()
    expect(generated.getCollectionCapabilities).toHaveBeenCalledOnce()
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({
      search: undefined, enabled: undefined, platform: undefined, offset: 0, limit: 20,
    })
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({ enabled: true, offset: 0, limit: 100 })
    expect(store.relevance?.keyword_pack_version).toBe(8)
  })

  it('loads the complete historical vehicle catalog without an active-only status filter', async () => {
    const firstPage = Array.from({ length: 200 }, (_, index) => ({
      ...historicalVehicle,
      id: `vehicle-${index}`,
      code: `A${index}`,
      display_name: `车型 ${index}`,
      status: index % 2 === 0 ? 'deprecated' as const : 'merged' as const,
    }))
    generated.listVehicleModels.mockImplementation(async (params: { offset?: number; limit?: number; status?: string }) => {
      if ((params.offset ?? 0) === 0) {
        return { items: firstPage, total: 201, catalog_version: 9, offset: 0, limit: 200 }
      }
      return { items: [historicalVehicle], total: 201, catalog_version: 9, offset: 200, limit: 200 }
    })
    const store = useCollectionStrategyStore()

    await store.refresh()

    expect(generated.listVehicleModels).toHaveBeenNthCalledWith(1, { offset: 0, limit: 200 })
    expect(generated.listVehicleModels).toHaveBeenNthCalledWith(2, { offset: 200, limit: 200 })
    expect(generated.listVehicleModels.mock.calls[0]?.[0]).not.toHaveProperty('status')
    expect(generated.listVehicleModels.mock.calls[1]?.[0]).not.toHaveProperty('status')
    expect((store as unknown as { vehicleCatalog: unknown[] }).vehicleCatalog).toHaveLength(201)
  })

  it('creates only a periodic Plan without a Plan-level Relevance override', async () => {
    generated.createCollectionPlan.mockResolvedValue({ id: 'plan-1' })
    await createPlan({
      name: '爱玛周期采集', schedule_expr: '0 9 * * *',
      platforms: [{
        platform: 'xiaohongshu', provider_config_id: 'provider-1',
        search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
      }],
      keyword_pack_ids: ['pack-1'], enabled: true,
    })
    expect(generated.createCollectionPlan).toHaveBeenCalledWith({
      name: '爱玛周期采集', schedule_expr: '0 9 * * *',
      platforms: [{
        platform: 'xiaohongshu', provider_config_id: 'provider-1',
        search_config: { sort_mode: 'latest', published_within: '1d', content_type: 'all' },
      }],
      keyword_pack_ids: ['pack-1'], enabled: true,
    })
    const payload = generated.createCollectionPlan.mock.calls[0]?.[0]
    expect(payload).not.toHaveProperty('schedule_mode')
    expect(payload).not.toHaveProperty('relevance_keyword_pack_id')
  })

  it('paginates the periodic Plan list through the formal offset contract', async () => {
    generated.listCollectionPlans.mockImplementation(async (params: { enabled?: boolean; offset?: number; limit?: number }) =>
      params.enabled === true
        ? { items: [], total: 0, enabled_count: 4, offset: 0, limit: 100 }
        : { items: [], total: 25, enabled_count: 4, offset: params.offset ?? 0, limit: params.limit ?? 20 },
    )
    const store = useCollectionStrategyStore()
    await store.refresh()
    await store.nextPlanPage()
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({
      search: undefined, enabled: undefined, platform: undefined, offset: 20, limit: 20,
    })
  })

  it('paginates keyword packs while keeping a complete API-backed catalog for cross-page references', async () => {
    generated.listKeywordPacks.mockImplementation(async (params: { offset?: number; limit?: number }) => {
      if (params.limit === 100) {
        return { items: [globalPack], total: 1, offset: params.offset ?? 0, limit: 100 }
      }
      return { items: [globalPack], total: 25, offset: params.offset ?? 0, limit: 20 }
    })
    const store = useCollectionStrategyStore()

    await store.refresh()

    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 20 })
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 100 })
    expect(store.packCatalog).toEqual([globalPack])
    expect(store.packLimit).toBe(20)

    await store.nextPackPage()
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 20, limit: 20 })
  })

  it('does not send a disable request for the keyword pack used by global relevance', async () => {
    generated.listKeywordPacks.mockResolvedValue({ items: [globalPack], total: 1, offset: 0, limit: 100 })
    generated.getGlobalRelevanceConfig.mockResolvedValue({
      keyword_pack_id: globalPack.id, keyword_pack_version: 1, version: 1,
      effective_keywords: ['爱玛'], updated_at: '2026-08-22T00:00:00Z',
    })
    const store = useCollectionStrategyStore()
    await store.refresh()
    await store.togglePack(globalPack)
    expect(generated.updateKeywordPackEnabled).not.toHaveBeenCalled()
    expect(store.error).toContain('全局相关性')
  })

  it('does not enable a Plan when global relevance is unavailable', async () => {
    generated.getGlobalRelevanceConfig.mockRejectedValue({ status: 409, detail: 'not configured', request_id: 'r1' })
    const store = useCollectionStrategyStore()
    await store.refresh()
    const plan: CollectionPlanResponse = {
      id: '33333333-3333-4333-8333-333333333333', name: '停用计划', enabled: false,
      schedule_expr: '0 9 * * *', timezone: 'Asia/Shanghai', schedule_version: 1,
      next_run_at: null, last_scheduled_at: null, detail_policy: 'on_change', comment_policy: 'adaptive',
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1', search_config: {} }],
      keyword_pack_ids: [globalPack.id], created_at: '2026-08-22T00:00:00Z', updated_at: '2026-08-22T00:00:00Z',
    }
    await store.togglePlan(plan)
    expect(generated.updateCollectionPlanEnabled).not.toHaveBeenCalled()
    expect(store.error).toContain('全局相关性')
  })
})
