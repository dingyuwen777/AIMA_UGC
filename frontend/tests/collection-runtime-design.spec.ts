import { readFile } from 'node:fs/promises'

import { createPinia } from 'pinia'
import { createSSRApp, h, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import CollectionRuntimePage from '../src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue'
import CollectionRuntimeFilters from '../src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeFilters.vue'
import CollectionRuntimeKpiCards from '../src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeKpiCards.vue'
import CollectionRuntimeTable from '../src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeTable.vue'

const blankRoute = { render: () => h('div') }

async function renderComponent(component: Component, props: Record<string, unknown> = {}): Promise<string> {
  const app = createSSRApp({ render: () => h(component, props) })
  app.use(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: blankRoute },
      { path: '/voice-plaza', component: blankRoute },
      { path: '/collection-runtime', component: blankRoute },
      { path: '/collection-strategy', component: blankRoute },
    ],
  })
  app.use(router)
  await router.push('/collection-runtime')
  await router.isReady()
  return renderToString(app)
}

async function readCollectionRuntimeSource(filename: string): Promise<string> {
  return readFile(
    new URL(
      `../src/features/import-batches/pages/CollectionRuntimePage/${filename}`,
      import.meta.url,
    ),
    'utf8',
  )
}

describe('采集运行中心正式 Figma 基线', () => {
  it('复用与采集策略相同的页面标题和按钮组件，并使用正式业务文案', async () => {
    const html = await renderComponent(CollectionRuntimePage)

    expect(html).toContain('class="aima-page-header"')
    expect(html.match(/class="aima-button/g)?.length ?? 0).toBeGreaterThanOrEqual(5)
    expect(html).toContain('统一查看数据导入与辅助补采运行')
    expect(html).toContain('新建辅助补采')
    expect(html).not.toContain('新建 TikHub 补采')
  })

  it('KPI 摘要行使用 Figma 的三个中文业务指标', async () => {
    const html = await renderComponent(CollectionRuntimeKpiCards, {
      summary: {
        processing_count: 2,
        completed_today_count: 6,
        contents_ingested_today: 124,
        as_of: '2026-08-28T08:00:00+08:00',
      },
      loading: false,
    })

    expect(html.match(/class="kpi-card/g)).toHaveLength(3)
    expect(html).toContain('处理中')
    expect(html).toContain('今日完成')
    expect(html).toContain('今日入库内容')
    expect(html).not.toContain('今日入库 Content')
  })

  it('筛选区按 Figma 顺序排列并隐藏 Cursor 实现细节', async () => {
    const html = await renderComponent(CollectionRuntimeFilters, {
      activeTab: 'all',
      search: '',
      status: '',
      recordType: '',
      stage: '',
      createdFrom: '',
      createdTo: '',
      'onUpdate:search': () => undefined,
      'onUpdate:status': () => undefined,
      'onUpdate:recordType': () => undefined,
      'onUpdate:stage': () => undefined,
      'onUpdate:createdFrom': () => undefined,
      'onUpdate:createdTo': () => undefined,
    })

    const searchIndex = html.indexOf('搜索批次名称、批次编号、运行编号')
    const dateIndex = html.indexOf('aria-label="开始日期"')
    const statusIndex = html.indexOf('aria-label="状态"')
    const typeIndex = html.indexOf('aria-label="类型"')
    const stageIndex = html.indexOf('aria-label="处理阶段"')

    expect(searchIndex).toBeGreaterThan(-1)
    expect(dateIndex).toBeGreaterThan(searchIndex)
    expect(statusIndex).toBeGreaterThan(dateIndex)
    expect(typeIndex).toBeGreaterThan(statusIndex)
    expect(stageIndex).toBeGreaterThan(typeIndex)
    expect(html).toContain('时间按北京时间解释')
    expect(html).not.toContain('Cursor')
    expect(html.match(/class="aima-button/g)).toHaveLength(2)
  })

  it('运行记录表按正式 Figma 固定为 7 列且不单独展示关联对象', async () => {
    const html = await renderComponent(CollectionRuntimeTable, {
      items: [],
      loading: false,
    })
    const headStart = html.indexOf('<div class="table-head">')
    const headEnd = html.indexOf('</div>', headStart)
    const tableHead = html.slice(headStart, headEnd)

    expect(headStart).toBeGreaterThan(-1)
    expect(tableHead.match(/<span>/g)).toHaveLength(7)
    expect(tableHead).toContain('任务 / 执行编号')
    expect(tableHead).toContain('类型')
    expect(tableHead).toContain('状态与进度')
    expect(tableHead).toContain('当前阶段')
    expect(tableHead).toContain('处理统计')
    expect(tableHead).toContain('创建时间')
    expect(tableHead).toContain('操作')
    expect(tableHead).not.toContain('关联对象')
  })

  it('Data Import Campaign 只在后端 can_start 为真时渲染开始导入动作', async () => {
    const source = await readCollectionRuntimeSource('components/DataImportDialog.vue')

    expect(source).toContain('v-if="store.selectedHistoricalCampaign.can_start"')
    expect(source).not.toContain(
      ':disabled="!store.selectedHistoricalCampaign.can_start || store.actingHistorical"',
    )
  })

  it('辅助补采产品与可访问文案不绑定具体 Provider 或后台实现名', async () => {
    const [drawerSource, pageSource] = await Promise.all([
      readCollectionRuntimeSource('components/TikHubSupplementDrawer.vue'),
      readCollectionRuntimeSource('CollectionRuntimePage.vue'),
    ])

    expect(drawerSource).toContain('aria-label="新建辅助补采"')
    expect(drawerSource).not.toContain('aria-label="新建 TikHub 辅助补采"')
    expect(pageSource).not.toContain('TikHub Collection Run / Job 已创建')
    expect(pageSource).not.toContain('Worker 在后台执行')
  })
})
