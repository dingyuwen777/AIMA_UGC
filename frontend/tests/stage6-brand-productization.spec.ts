import { readFile } from 'node:fs/promises'

import { describe, expect, it } from 'vitest'

async function readSource(path: string): Promise<string> {
  return readFile(new URL(`../src/${path}`, import.meta.url), 'utf8')
}

describe('Stage 6 品牌车型过滤前端产品化', () => {
  it('管理员配置只保留五个目标入口并退出词包车型关联调用', async () => {
    const [page, api] = await Promise.all([
      readSource('features/admin-configuration/pages/AdminConfigurationPage.vue'),
      readSource('features/admin-configuration/api.ts'),
    ])

    for (const label of ['品牌与车型', 'AI 模型', 'TikHub', 'AI 分析规则', '操作记录']) {
      expect(page).toContain(label)
    }
    expect(page).not.toContain("['links', '词包关联']")
    expect(api).not.toContain('replaceKeywordPackVehicleModels')
    expect(api).not.toContain('listKeywordPacks')
    expect(api).toContain('createVehicleBrand')
    expect(api).toContain('addVehicleBrandAlias')
  })

  it('采集计划使用关键词包搜索与品牌过滤，新建流程不再提交车型搜索资源', async () => {
    const [page, drawer] = await Promise.all([
      readSource('features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue'),
      readSource('features/collection-strategy/pages/CollectionStrategyPage/components/PlanCreateDrawer.vue'),
    ])

    expect(page).not.toContain("{ value: 'relevance', label: '全局相关性' }")
    expect(drawer).toContain('搜索条件：关键词包')
    expect(drawer).toContain('内容过滤条件：品牌')
    expect(drawer).toContain('brand_ids: selectedBrands.value')
    expect(drawer).not.toContain('vehicle_model_ids: selectedVehicles.value')
  })

  it('Excel 与 TikHub Discovery 都提交品牌过滤，补采不携带搜索或过滤范围', async () => {
    const [dataImport, discovery] = await Promise.all([
      readSource('features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue'),
      readSource('features/import-batches/pages/CollectionRuntimePage/components/TikHubSupplementDrawer.vue'),
    ])

    expect(dataImport).toContain('不适用于 Excel 文件导入')
    expect(dataImport).toContain('brand_ids: selectedBrandIds.value')
    expect(discovery).toContain('brand_ids: mode.value === \'discovery\' ? selectedBrandIds.value : []')
    expect(discovery).not.toContain('vehicle_model_ids: mode.value === \'discovery\'')
  })

  it('声音广场发送品牌与竞争范围筛选并展示品牌证据', async () => {
    const [store, filters, detail] = await Promise.all([
      readSource('features/voice-plaza/store.ts'),
      readSource('features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaFilters.vue'),
      readSource('features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue'),
    ])

    expect(store).toContain('brand_ids: filters.brandIds')
    expect(store).toContain('competition_scopes: filters.competitionScopes')
    expect(filters).toContain('品牌')
    expect(filters).toContain('竞争范围')
    expect(detail).toContain('品牌识别证据')
    expect(detail).toContain('车型识别证据')
  })
})
