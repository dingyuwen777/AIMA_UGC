import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { createSSRApp, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchWorkbenchTaxonomy: vi.fn(),
  fetchWorkbenchStream: vi.fn(),
  fetchWorkbenchTrend: vi.fn(),
  fetchWorkbenchMind: vi.fn(),
  fetchWorkbenchLayout: vi.fn(),
  saveWorkbenchLayout: vi.fn(),
  fetchActiveBrands: vi.fn(),
  fetchActiveVehicleModels: vi.fn(),
}))
vi.mock('../src/features/workbench/api', () => api)

import WorkbenchPage from '../src/features/workbench/pages/WorkbenchPage.vue'
import { useWorkbenchStore } from '../src/features/workbench/store'

const schemeId = '11111111-1111-4111-8111-111111111111'
const taxonomyHash = 'a'.repeat(64)
const taxonomy = {
  prompt_version: 'content-labeling.v4',
  prompt_sha256: 'b'.repeat(64),
  schema_version: 'aima-content-taxonomy.v2',
  taxonomy_sha256: taxonomyHash,
  sentiments: ['正面', '中性', '负面', '混合', '无法判断'],
  voice_types: ['真实用户发声', '品牌官方发声', '无法判断'],
  labels: [
    { primary_label: '外观设计', secondary_labels: ['颜色与配色', '整体造型与颜值'] },
    { primary_label: '电池、续航与充电', secondary_labels: ['续航里程'] },
    { primary_label: '无法分类', secondary_labels: ['无法判断'] },
  ],
}
const layout = {
  schema_version: 1 as const,
  revision: 3,
  updated_at: '2026-09-27T08:00:00+08:00',
  modules: [
    { module_id: 'sound-stream' as const, visible: true, order: 0, column_span: 6, row_units: 48 },
    { module_id: 'brand-mind' as const, visible: true, order: 1, column_span: 6, row_units: 48 },
    { module_id: 'ugc-trend' as const, visible: true, order: 2, column_span: 6, row_units: 48 },
  ],
}
const stream = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  items: [],
}
const mind = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  date_from: '2026-08-29',
  date_to: '2026-09-27',
  previous_date_from: '2026-07-30',
  previous_date_to: '2026-08-28',
  identified_user_count: 100,
  unidentified_content_count: 2,
  analyzed_count: 80,
  analysis_coverage_rate: 0.8,
  dimensions: [
    {
      primary_label: '外观设计',
      user_count: 35,
      user_share: 0.35,
      positive_rate: 0.7,
      user_share_change_pp: 2.2,
      secondary_labels: [{ secondary_label: '颜色与配色', user_count: 20 }],
      change_summary: '外观设计用户占比较紧邻等长上期上升 2.20pp。',
    },
    {
      primary_label: '电池、续航与充电',
      user_count: 28,
      user_share: 0.28,
      positive_rate: 0.55,
      user_share_change_pp: -1.1,
      secondary_labels: [{ secondary_label: '续航里程', user_count: 18 }],
      change_summary: '电池、续航与充电用户占比较紧邻等长上期下降 1.10pp。',
    },
  ],
}
const trend = {
  analysis_scheme_version_id: schemeId,
  taxonomy_sha256: taxonomyHash,
  as_of: '2026-09-27T08:10:00+08:00',
  date_from: '2026-08-29',
  date_to: '2026-09-27',
  previous_date_from: '2026-07-30',
  previous_date_to: '2026-08-28',
  total_count: 120,
  daily_average: 4,
  peak_day: '2026-09-20',
  peak_count: 12,
  period_change_rate: 0.12,
  positive_rate: 0.6,
  positive_rate_change_pp: 3.2,
  analyzed_count: 100,
  analysis_coverage_rate: 0.833333,
  daily: [{ day: '2026-09-20', count: 12 }],
  sentiments: [
    { sentiment: '正面', count: 60, share: 0.6 },
    { sentiment: '混合', count: 10, share: 0.1 },
    { sentiment: '无法判断', count: 5, share: 0.05 },
  ],
  summary: '09/20 为当前周期声量峰值。',
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  api.fetchWorkbenchTaxonomy.mockResolvedValue(taxonomy)
  api.fetchActiveBrands.mockResolvedValue([])
  api.fetchActiveVehicleModels.mockResolvedValue([])
  api.fetchWorkbenchLayout.mockResolvedValue(layout)
  api.fetchWorkbenchStream.mockResolvedValue(stream)
  api.fetchWorkbenchMind.mockResolvedValue(mind)
  api.fetchWorkbenchTrend.mockResolvedValue(trend)
  api.saveWorkbenchLayout.mockImplementation(async (request: { revision: number; modules: typeof layout.modules }) => ({
    schema_version: 1,
    revision: request.revision + 1,
    updated_at: '2026-09-27T08:11:00+08:00',
    modules: request.modules,
  }))
})

describe('工作台状态与 Figma 基线', () => {
  it('动态消费 active Taxonomy，并保持三个模块同一 Scheme Version', async () => {
    const store = useWorkbenchStore()
    await store.initialize()

    expect(store.taxonomy?.taxonomy_sha256).toBe(taxonomyHash)
    expect(store.primaryLabelOptions.map((item) => item.primary_label)).toEqual([
      '外观设计',
      '电池、续航与充电',
    ])
    expect(store.activeSchemeVersionId).toBe(schemeId)
    expect(store.activeMind?.primary_label).toBe('外观设计')
  })

  it('编辑态只改草稿，取消恢复；保存时一次提交 revision CAS', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.startEditing()
    store.reorderModule('ugc-trend', 'sound-stream')
    store.setModuleVisible('brand-mind', false)

    expect(store.currentModules[0]?.module_id).toBe('ugc-trend')
    expect(store.hiddenModules.map((item) => item.module_id)).toEqual(['brand-mind'])

    store.cancelEditing()
    expect(store.currentModules.map((item) => item.module_id)).toEqual([
      'sound-stream',
      'brand-mind',
      'ugc-trend',
    ])
    expect(store.hiddenModules).toEqual([])

    store.startEditing()
    store.reorderModule('ugc-trend', 'sound-stream')
    expect(await store.saveLayout()).toBe(true)
    expect(api.saveWorkbenchLayout).toHaveBeenCalledTimes(1)
    expect(api.saveWorkbenchLayout.mock.calls[0]?.[0].revision).toBe(3)
    expect(store.layout?.revision).toBe(4)
    expect(store.editing).toBe(false)
  })

  it('每个模块按独立草稿以单列和单行粒度调整尺寸', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.startEditing()

    store.resizeModule('ugc-trend', 8.4, 63.6)

    expect(store.currentModules.find((item) => item.module_id === 'ugc-trend')).toEqual(
      expect.objectContaining({ column_span: 8, row_units: 64 }),
    )
    expect(store.currentModules.find((item) => item.module_id === 'sound-stream')).toEqual(
      expect.objectContaining({ column_span: 6, row_units: 48 }),
    )
    expect(store.currentModules.find((item) => item.module_id === 'brand-mind')).toEqual(
      expect.objectContaining({ column_span: 6, row_units: 48 }),
    )
  })

  it('active Taxonomy 切换后自动移除失效 AI 筛选值', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    store.setFilters({
      ...store.filters,
      sentiments: ['正面', '已删除情感'],
      voiceTypes: ['真实用户发声', '已删除发声'],
      primaryLabels: ['外观设计', '已删除一级'],
      secondaryLabels: ['颜色与配色', '已删除二级'],
    })

    await store.refreshTaxonomy()

    expect(store.filters.sentiments).toEqual(['正面'])
    expect(store.filters.voiceTypes).toEqual(['真实用户发声'])
    expect(store.filters.primaryLabels).toEqual(['外观设计'])
    expect(store.filters.secondaryLabels).toEqual(['颜色与配色'])
  })

  it('反向日期在进入三个模块请求前统一规范为有序区间', async () => {
    const store = useWorkbenchStore()
    store.setFilters({ ...store.filters, dateFrom: '2026-08-29', dateTo: '2026-08-28' })
    expect(store.filters.dateFrom).toBe('2026-08-28')
    expect(store.filters.dateTo).toBe('2026-08-29')
    await store.refreshData()
    for (const call of [api.fetchWorkbenchStream, api.fetchWorkbenchMind, api.fetchWorkbenchTrend]) {
      expect(call).toHaveBeenCalledWith(expect.objectContaining({
        date_from: '2026-08-28',
        date_to: '2026-08-29',
      }))
    }
  })

  it('声音流和趋势先返回时无需等待较慢的品牌心智请求', async () => {
    let finishMind: (value: typeof mind) => void = () => {}
    api.fetchWorkbenchMind.mockImplementation(() => new Promise<typeof mind>((resolve) => {
      finishMind = resolve
    }))
    const store = useWorkbenchStore()
    const pending = store.refreshData()
    await Promise.resolve()
    await Promise.resolve()
    expect(store.stream).toEqual(stream)
    expect(store.trend).toEqual(trend)
    expect(store.moduleLoading.mind).toBe(true)
    finishMind(mind)
    await pending
    expect(store.mind).toEqual(mind)
    expect(store.moduleLoading.mind).toBe(false)
  })

  it('active Scheme 切换时不会展示混合口径的三个模块', async () => {
    const store = useWorkbenchStore()
    await store.initialize()
    const nextStream = {
      ...stream,
      analysis_scheme_version_id: '22222222-2222-4222-8222-222222222222',
      taxonomy_sha256: 'c'.repeat(64),
    }
    api.fetchWorkbenchStream.mockResolvedValue(nextStream)
    api.fetchWorkbenchMind.mockRejectedValue(new Error('mind unavailable'))
    api.fetchWorkbenchTrend.mockRejectedValue(new Error('trend unavailable'))

    await store.refreshData()

    expect(api.fetchWorkbenchStream).toHaveBeenCalledTimes(2)
    expect(store.stream).toEqual(nextStream)
    expect(store.mind).toBeNull()
    expect(store.trend).toBeNull()
    expect(store.globalError).toContain('Taxonomy 暂未同步')
  })

  it('正式页面呈现动态心智和情感结构，不再展示首页占位图', async () => {
    const pinia: Pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkbenchStore(pinia)
    store.taxonomy = taxonomy
    store.layout = layout
    store.stream = stream
    store.mind = mind
    store.trend = trend
    store.selectedMind = '外观设计'

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { render: () => h('div') } },
        { path: '/voice-plaza', component: { render: () => h('div') } },
        { path: '/collection-runtime', component: { render: () => h('div') } },
        { path: '/collection-strategy', component: { render: () => h('div') } },
        { path: '/admin/configuration', component: { render: () => h('div') } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const app = createSSRApp({ render: () => h(WorkbenchPage) })
    app.use(pinia)
    app.use(router)
    const html = await renderToString(app)

    expect(html).toContain('工作台')
    expect(html).toContain('基于当前 active Taxonomy')
    expect(html).toContain('外观设计')
    expect(html).toContain('电池、续航与充电')
    expect(html).toContain('混合')
    expect(html).toContain('无法判断')
    expect(html).toContain('编辑工作台')
    expect(html).not.toContain('工作台开发中')
    expect(html).not.toContain('品牌印象')
    expect(html).not.toContain('设计审美')
  })
})
