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
    platform: 'all',
    enabled: true,
    priority: 100,
    note: '',
  }],
}

describe('collection strategy feature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    generated.listKeywordPacks.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 })
    generated.listCollectionPlans.mockResolvedValue({ items: [], total: 0, enabled_count: 0, offset: 0, limit: 20 })
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

  it('loads packs, global relevance, capabilities, and plans as one workspace', async () => {
    const store = useCollectionStrategyStore()
    await store.refresh()
    expect(generated.listKeywordPacks).toHaveBeenCalledOnce()
    expect(generated.getGlobalRelevanceConfig).toHaveBeenCalledOnce()
    expect(generated.getCollectionCapabilities).toHaveBeenCalledOnce()
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({
      search: undefined, enabled: undefined, platform: undefined, offset: 0, limit: 20,
    })
    expect(generated.listCollectionPlans).toHaveBeenCalledWith({ enabled: true, offset: 0, limit: 100 })
    expect(store.relevance?.keyword_pack_version).toBe(8)
  })

  it('creates only a periodic Plan without a Plan-level Relevance override', async () => {
    generated.createCollectionPlan.mockResolvedValue({ id: 'plan-1' })
    await createPlan({
      name: '爱玛周期采集', schedule_expr: '0 9 * * *',
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      keyword_pack_ids: ['pack-1'], enabled: true,
    })
    expect(generated.createCollectionPlan).toHaveBeenCalledWith({
      name: '爱玛周期采集', schedule_expr: '0 9 * * *',
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
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
    expect(store.error).toContain('全局 Relevance')
  })

  it('does not enable a Plan when global relevance is unavailable', async () => {
    generated.getGlobalRelevanceConfig.mockRejectedValue({ status: 409, detail: 'not configured', request_id: 'r1' })
    const store = useCollectionStrategyStore()
    await store.refresh()
    const plan: CollectionPlanResponse = {
      id: '33333333-3333-4333-8333-333333333333', name: '停用计划', enabled: false,
      schedule_expr: '0 9 * * *', timezone: 'Asia/Shanghai', schedule_version: 1,
      next_run_at: null, last_scheduled_at: null, detail_policy: 'on_change', comment_policy: 'adaptive',
      platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1' }],
      keyword_pack_ids: [globalPack.id], created_at: '2026-08-22T00:00:00Z', updated_at: '2026-08-22T00:00:00Z',
    }
    await store.togglePlan(plan)
    expect(generated.updateCollectionPlanEnabled).not.toHaveBeenCalled()
    expect(store.error).toContain('全局 Relevance')
  })
})