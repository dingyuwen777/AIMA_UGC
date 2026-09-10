import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CollectionPlanResponse } from '../src/generated/api/client'

const generated = vi.hoisted(() => ({
  listKeywordPacks: vi.fn(),
  createKeywordPack: vi.fn(),
  getKeywordPack: vi.fn(),
  updateKeywordPackEnabled: vi.fn(),
  addKeywordToPack: vi.fn(),
  getCollectionCapabilities: vi.fn(),
  listCollectionPlans: vi.fn(),
  createCollectionPlan: vi.fn(),
  getCollectionPlan: vi.fn(),
  updateCollectionPlanEnabled: vi.fn(),
  listVehicleModels: vi.fn(),
  listVehicleBrands: vi.fn(),
}))

vi.mock('../src/generated/api/client', () => generated)

import { createPlan, fetchKeywordPacks } from '../src/features/collection-strategy/api'
import { planExecutionReason } from '../src/features/collection-strategy/eligibility'
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
    generated.listVehicleBrands.mockResolvedValue({ items: [], total: 0, catalog_version: 1, offset: 0, limit: 200 })
    generated.getCollectionCapabilities.mockResolvedValue({ provider_configs: [], capabilities: [] })
    generated.getKeywordPack.mockResolvedValue(packDetail)
  })

  it('delegates keyword pack listing to the generated Orval client', async () => {
    await fetchKeywordPacks({ search: '爱玛', enabled: true, offset: 0, limit: 20 })
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ search: '爱玛', enabled: true, offset: 0, limit: 20 })
  })

  it('loads packs, complete brands, historical vehicles, capabilities, and plans as one workspace', async () => {
    const store = useCollectionStrategyStore()
    await store.refresh()
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 20 })
    expect(generated.listKeywordPacks).toHaveBeenCalledWith({ offset: 0, limit: 100 })
    expect(generated.listVehicleModels).toHaveBeenCalledWith({ offset: 0, limit: 200 })
    expect(generated.listVehicleBrands).toHaveBeenCalledWith({ offset: 0, limit: 200 })
    expect(generated.getCollectionCapabilities).toHaveBeenCalledOnce()
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({
      search: undefined, enabled: undefined, platform: undefined, offset: 0, limit: 20,
    })
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({ enabled: true, offset: 0, limit: 100 })
    expect(store.brandCatalog).toEqual([])
  })

  it('keeps deprecated brands available for historical plan display without counting them as enabled', async () => {
    const deprecatedBrand = {
      id: '77777777-7777-4777-8777-777777777777',
      code: 'HISTORICAL',
      display_name: '历史品牌',
      role: 'competitor' as const,
      status: 'deprecated' as const,
      version: 2,
      catalog_version: 9,
      aliases: [],
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-28T00:00:00Z',
    }
    generated.listVehicleBrands.mockImplementation(async (params: { status?: string }) => ({
      items: params.status === 'active' ? [] : [deprecatedBrand],
      total: params.status === 'active' ? 0 : 1,
      catalog_version: 9,
      offset: 0,
      limit: 200,
    }))
    const store = useCollectionStrategyStore()

    await store.refresh()

    expect(store.brandCatalog).toEqual([deprecatedBrand])
    expect(store.enabledBrandCount).toBe(0)
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

  it('requires Keyword Pack search terms even when a legacy vehicle scope exists', () => {
    expect(planExecutionReason({
      keywordPackIds: [],
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      packDetails: {},
      capabilities: { provider_configs: [], capabilities: [] },
    })).toBe('请至少选择一个关键词包作为搜索条件。')
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

  it('does not disable a keyword pack referenced by an enabled plan', async () => {
    generated.listKeywordPacks.mockResolvedValue({ items: [globalPack], total: 1, offset: 0, limit: 100 })
    generated.listCollectionPlans.mockImplementation(async (params: { enabled?: boolean }) => params.enabled
      ? { items: [{ keyword_pack_ids: [globalPack.id] }], total: 1, enabled_count: 1, offset: 0, limit: 100 }
      : { items: [], total: 0, enabled_count: 1, offset: 0, limit: 20 })
    const store = useCollectionStrategyStore()
    await store.refresh()
    await store.togglePack(globalPack)
    expect(generated.updateKeywordPackEnabled).not.toHaveBeenCalled()
    expect(store.error).toContain('启用中的采集计划')
  })

  it('enables a valid Plan without reading legacy global relevance', async () => {
    generated.getCollectionCapabilities.mockResolvedValue({
      provider_configs: [{ id: 'provider-1', provider: 'tikhub', display_name: 'TikHub' }],
      capabilities: [{
        platform: 'xiaohongshu', provider: 'tikhub', operations: ['keyword_search'], search: null,
      }],
    })
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
    expect(generated.updateCollectionPlanEnabled).toHaveBeenCalledWith(plan.id, { enabled: true })
    expect(store.error).toBeNull()
  })

  it('keeps the latest selected pack when older detail requests finish later', async () => {
    const store = useCollectionStrategyStore()
    let finishOlder!: (value: typeof packDetail) => void
    generated.getKeywordPack.mockReturnValueOnce(new Promise((resolve) => { finishOlder = resolve }))
    const older = store.openPack('older')
    generated.getKeywordPack.mockResolvedValueOnce({ ...packDetail, id: 'newer', name: '当前选择' })
    await store.openPack('newer')
    finishOlder({ ...packDetail, id: 'older', name: '旧选择' })
    await older
    expect(store.selectedPack?.id).toBe('newer')
  })

  it('does not overwrite a newer refresh with an older response', async () => {
    const store = useCollectionStrategyStore()
    let finishOlder!: (value: unknown) => void
    generated.listVehicleBrands.mockReturnValueOnce(new Promise((resolve) => { finishOlder = resolve }))
    const older = store.refresh()
    generated.listVehicleBrands.mockResolvedValueOnce({ items: [{ id: 'latest' }], total: 1, catalog_version: 2, offset: 0, limit: 200 })
    await store.refresh()
    finishOlder({ items: [{ id: 'older' }], total: 1, catalog_version: 1, offset: 0, limit: 200 })
    await older
    expect(store.brandCatalog[0]?.id).toBe('latest')
  })

  it('keeps refreshed pack details when an older cache request finishes later', async () => {
    const store = useCollectionStrategyStore()
    let finishOlder!: (value: typeof packDetail) => void
    generated.getKeywordPack.mockReturnValueOnce(new Promise((resolve) => { finishOlder = resolve }))
    const older = store.loadPackDetails([packDetail.id])
    await store.refresh()
    generated.getKeywordPack.mockResolvedValueOnce({ ...packDetail, version: 99 })
    await store.loadPackDetails([packDetail.id])
    finishOlder({ ...packDetail, version: 1 })
    await older
    expect(store.packDetails[packDetail.id]?.version).toBe(99)
  })

  it('ignores an older pack page after a workspace refresh', async () => {
    const store = useCollectionStrategyStore()
    store.packTotal = 25
    let finishOlder!: (value: unknown) => void
    generated.listKeywordPacks.mockReturnValueOnce(new Promise((resolve) => { finishOlder = resolve }))
    const older = store.nextPackPage()
    await store.refresh()
    finishOlder({ items: [globalPack], total: 25, offset: 20, limit: 20 })
    await older
    expect(store.packs).toEqual([])
    expect(store.packTotal).toBe(0)
    expect(store.selectedPack).toBeNull()
  })
})
