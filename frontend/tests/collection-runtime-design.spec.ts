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

  it('筛选区按业务条件排列，不诱导用户输入 Batch、Run 或 Cursor 等工程身份', async () => {
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

    const searchIndex = html.indexOf('搜索来源文件或采集关键词')
    const dateIndex = html.indexOf('aria-label="开始日期"')
    const statusIndex = html.indexOf('aria-label="状态"')
    const typeIndex = html.indexOf('aria-label="类型"')
    const stageIndex = html.indexOf('aria-label="处理阶段"')

    expect(searchIndex).toBeGreaterThan(-1)
    expect(dateIndex).toBeGreaterThan(searchIndex)
    expect(statusIndex).toBeGreaterThan(dateIndex)
    expect(typeIndex).toBeGreaterThan(statusIndex)
    expect(stageIndex).toBeGreaterThan(typeIndex)
    expect(html).toContain('时间按北京时间显示')
    expect(html).not.toContain('批次编号')
    expect(html).not.toContain('运行编号')
    expect(html).not.toContain('Cursor')
    expect(html).not.toContain('TikHub 采集中')
    expect(html).not.toContain('不可变快照')
    expect(html.match(/class="aima-button/g)).toHaveLength(2)
  })

  it('运行记录表固定为 7 列，只展示业务任务身份而不显示内部 UUID', async () => {
    const recordId = '52345678-1234-5678-1234-567812345678'
    const html = await renderComponent(CollectionRuntimeTable, {
      items: [{
        record_id: recordId,
        record_type: 'tikhub_discovery',
        display_name: '爱玛品牌内容发现',
        job_id: '62345678-1234-5678-1234-567812345678',
        status: 'running',
        stage: 'content_discovery',
        progress: 50,
        collection_stats: {
          requested_count: 20,
          succeeded_count: 10,
          failed_count: 0,
          content_count: 8,
          comment_count: 12,
          filtered_count: 2,
        },
        created_at: '2026-09-07T08:00:00+08:00',
        started_at: '2026-09-07T08:00:10+08:00',
        finished_at: null,
      }],
      loading: false,
    })
    const headMatch = html.match(/<div[^>]*class="table-head"[^>]*>([\s\S]*?)<\/div>/)
    const tableHead = headMatch?.[1] ?? ''

    expect(headMatch).not.toBeNull()
    expect(tableHead.match(/<span(?:\s[^>]*)?>/g)).toHaveLength(7)
    expect(tableHead).toContain('任务')
    expect(tableHead).toContain('类型')
    expect(tableHead).toContain('状态与进度')
    expect(tableHead).toContain('当前阶段')
    expect(tableHead).toContain('处理结果')
    expect(tableHead).toContain('创建时间')
    expect(tableHead).toContain('操作')
    expect(tableHead).not.toContain('任务 / 执行编号')
    expect(tableHead).not.toContain('关联对象')
    expect(html).toContain('爱玛品牌内容发现')
    expect(html).toContain('平台采集')
    expect(html).not.toContain(recordId)
    expect(html).not.toContain('TikHub 发现')
  })

  it('导入和补采详情把内部 ID、错误码与后台任务信息下沉到技术详情', async () => {
    const [importSource, runSource] = await Promise.all([
      readCollectionRuntimeSource('components/ImportBatchDetailDrawer.vue'),
      readCollectionRuntimeSource('components/CollectionRunDetailDrawer.vue'),
    ])

    expect(importSource).toContain('aria-label="数据导入详情"')
    expect(importSource).toContain('<summary>技术详情</summary>')
    expect(importSource).toContain('导入 ID')
    expect(importSource).not.toContain('后台任务状态')
    expect(importSource).not.toContain('上传与 Artifact')
    expect(importSource).not.toContain('Worker 持续执行')
    expect(runSource).toContain('aria-label="辅助补采详情"')
    expect(runSource).toContain('<summary>技术详情</summary>')
    expect(runSource).toContain('运行 ID')
    expect(runSource).not.toContain('TikHub 运行详情')
    expect(runSource).not.toContain('基于已有批次补采')
  })

  it('Data Import Campaign 只在后端 can_start 为真时渲染开始导入动作', async () => {
    const source = await readCollectionRuntimeSource('components/DataImportDialog.vue')

    expect(source).toContain('v-if="store.selectedHistoricalCampaign.can_start"')
    expect(source).not.toContain(
      ':disabled="!store.selectedHistoricalCampaign.can_start || store.actingHistorical"',
    )
  })

  it('导入任务详情沿用采集运行中心约 5 秒的条件轮询节奏', async () => {
    const source = await readCollectionRuntimeSource('components/DataImportDialog.vue')

    expect(source).toContain('const campaignPollIntervalMs = 5_000')
    expect(source).toContain('setInterval(() => void pollCampaign(), campaignPollIntervalMs)')
    expect(source).not.toContain('setInterval(() => void pollCampaign(), 1_000)')
  })

  it('任务中心失败导入深链会定位到对应导入任务，而不是只打开运行中心首页', async () => {
    const pageSource = await readCollectionRuntimeSource('CollectionRuntimePage.vue')
    const taskCenterSource = await readFile(
      new URL('../src/features/task-center/store.ts', import.meta.url),
      'utf8',
    )

    expect(taskCenterSource).toContain('/collection-runtime?data_import_campaign_id=')
    expect(taskCenterSource).toContain("actionLabel: hasImportFailure ? '处理失败项' : '查看'")
    expect(pageSource).toContain('route.query.data_import_campaign_id')
    expect(pageSource).toContain('await store.refreshHistoricalCampaign(campaignId)')
    expect(pageSource).toContain('指定导入任务暂不可打开，请从列表重新选择。')
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
