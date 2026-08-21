import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

describe('collection strategy feature', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    generated.listKeywordPacks.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 100 })
    generated.listCollectionPlans.mockResolvedValue({
      items: [],
      total: 0,
      enabled_count: 0,
      offset: 0,
      limit: 20,
    })
    generated.getCollectionCapabilities.mockResolvedValue({
      provider_configs: [],
      capabilities: [],
    })
    generated.getGlobalRelevanceConfig.mockResolvedValue({
      keyword_pack_id: 'pack-global',
      keyword_pack_version: 8,
      version: 3,
      effective_keywords: ['爱玛'],
      updated_at: '2026-08-21T00:00:00Z',
    })
  })

  it('delegates keyword pack listing to the generated Orval client', async () => {
    await fetchKeywordPacks({ search: '爱玛', enabled: true, offset: 0, limit: 20 })

    expect(generated.listKeywordPacks).toHaveBeenCalledWith({
      search: '爱玛',
      enabled: true,
      offset: 0,
      limit: 20,
    })
  })

  it('loads packs, global relevance, capabilities, and plans as one workspace', async () => {
    const store = useCollectionStrategyStore()

    await store.refresh()

    expect(generated.listKeywordPacks).toHaveBeenCalledOnce()
    expect(generated.getGlobalRelevanceConfig).toHaveBeenCalledOnce()
    expect(generated.getCollectionCapabilities).toHaveBeenCalledOnce()
    expect(generated.listCollectionPlans).toHaveBeenCalledOnce()
    expect(store.relevance?.keyword_pack_version).toBe(8)
  })

  it('creates only a periodic Plan without a Plan-level Relevance override', async () => {
    generated.createCollectionPlan.mockResolvedValue({ id: 'plan-1' })

    await createPlan({
      name: '爱玛周期采集',
      schedule_expr: '0 9 * * *',
      platforms: [{ platform: 'xhs', provider_config_id: 'provider-1' }],
      keyword_pack_ids: ['pack-1'],
      enabled: true,
    })

    expect(generated.createCollectionPlan).toHaveBeenCalledWith({
      name: '爱玛周期采集',
      schedule_expr: '0 9 * * *',
      platforms: [{ platform: 'xhs', provider_config_id: 'provider-1' }],
      keyword_pack_ids: ['pack-1'],
      enabled: true,
    })
    const payload = generated.createCollectionPlan.mock.calls[0]?.[0]
    expect(payload).not.toHaveProperty('schedule_mode')
    expect(payload).not.toHaveProperty('relevance_keyword_pack_id')
  })

  it('paginates the periodic Plan list through the formal offset contract', async () => {
    generated.listCollectionPlans.mockResolvedValue({
      items: [],
      total: 25,
      enabled_count: 4,
      offset: 0,
      limit: 20,
    })
    const store = useCollectionStrategyStore()
    await store.refresh()

    await store.nextPlanPage()

    expect(generated.listCollectionPlans).toHaveBeenLastCalledWith({
      search: undefined,
      enabled: undefined,
      platform: undefined,
      offset: 20,
      limit: 20,
    })
  })
})
