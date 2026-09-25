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
import DataImportDialog from '../src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue'
import { useImportBatchesStore } from '../src/features/import-batches/store'

const blankRoute = { render: () => h('div') }

async function renderComponent(
  component: Component,
  props: Record<string, unknown> = {},
  setupStore?: (pinia: ReturnType<typeof createPinia>) => void,
): Promise<string> {
  const app = createSSRApp({ render: () => h(component, props) })
  const pinia = createPinia()
  app.use(pinia)
  setupStore?.(pinia)
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
  const context: { teleports?: Record<string, string> } = {}
  const html = await renderToString(app, context)
  return html + Object.values(context.teleports ?? {}).join('')
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
  it('复用公共页面标题和按钮组件，并使用正式业务文案', async () => {
    const html = await renderComponent(CollectionRuntimePage)

    expect(html).toMatch(/class="[^"]*\baima-page-header\b[^"]*"/)
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
    expect(html).toContain('今日任务入库量')
    expect(html).toContain('各任务累计，可能包含重复内容')
  })

  it('默认筛选只展示任务、北京时间日期、状态和类型，不暴露内部处理阶段', async () => {
    const html = await renderComponent(CollectionRuntimeFilters, {
      activeTab: 'all',
      search: '',
      status: '',
      recordType: '',
      createdFrom: '',
      createdTo: '',
      'onUpdate:search': () => undefined,
      'onUpdate:status': () => undefined,
      'onUpdate:recordType': () => undefined,
      'onUpdate:createdFrom': () => undefined,
      'onUpdate:createdTo': () => undefined,
    })

    const searchIndex = html.indexOf('搜索任务名称或来源文件')
    const dateIndex = html.indexOf('aria-label="创建时间范围"')
    const statusIndex = html.indexOf('aria-label="状态"')
    const typeIndex = html.indexOf('aria-label="类型"')

    expect(searchIndex).toBeGreaterThan(-1)
    expect(dateIndex).toBeGreaterThan(searchIndex)
    expect(statusIndex).toBeGreaterThan(dateIndex)
    expect(typeIndex).toBeGreaterThan(statusIndex)
    expect(html).toContain('按任务名称、创建时间、状态和类型筛选')
    expect(html).not.toContain('aria-label="处理阶段"')
    expect(html).not.toContain('批次编号')
    expect(html).not.toContain('运行编号')
    expect(html).not.toContain('Cursor')
    const filterActions = html.slice(html.indexOf('class="filter-actions"'))
    expect(filterActions.match(/class="aima-button/g)).toHaveLength(2)
  })

  it('运行记录表固定为 7 列，使用产品语义与状态进度组件而不显示内部 UUID', async () => {
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
        keywords: ['爱玛品牌'],
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
      error: null,
    })
    const headMatch = html.match(/<div[^>]*class="table-head"[^>]*>([\s\S]*?)<\/div>/)
    const tableHead = headMatch?.[1] ?? ''

    expect(headMatch).not.toBeNull()
    expect(tableHead.match(/<span(?:\s[^>]*)?>/g)).toHaveLength(7)
    expect(tableHead).toContain('任务')
    expect(tableHead).toContain('类型')
    expect(tableHead).toContain('状态与进度')
    expect(tableHead).toContain('处理环节')
    expect(tableHead).toContain('处理结果')
    expect(tableHead).toContain('创建时间')
    expect(tableHead).toContain('操作')
    expect(tableHead).not.toContain('任务 / 执行编号')
    expect(tableHead).not.toContain('关联对象')
    expect(html).toContain('爱玛品牌内容发现')
    expect(html).toContain('关键词：爱玛品牌')
    expect(html).toContain('status-pill')
    expect(html).not.toContain(recordId)
  })

  it('第二次历史重筛新增为零时仍展示处理已有记录的数量', async () => {
    const html = await renderComponent(CollectionRuntimeTable, {
      items: [{
        record_id: 'replay-2',
        record_type: 'canonical_replay',
        display_name: '历史数据重筛',
        status: 'succeeded',
        stage: 'succeeded',
        progress: 100,
        created_at: '2026-09-25T09:36:32+08:00',
        canonical_replay_stats: {
          artifact_count: 223, run_count: 3, queued_run_count: 0, running_run_count: 0,
          succeeded_run_count: 3, failed_run_count: 0, cancelled_run_count: 0,
          rows_seen: 437099, rows_matched: 47179, rows_filtered_out: 389920,
          duplicates_removed: 6875, rows_ingested: 0, existing_convergence: 40304,
          reversible: true, lifecycle_status: 'active', reversal_job_id: null,
          reverted_content_count: 0, hidden_content_count: 0, retained_content_count: 0,
          skipped_content_count: 0, restored_evidence_count: 0, skipped_evidence_count: 0,
        },
      }],
      loading: false,
      error: null,
    })

    expect(html).toContain('新增记录 0 条')
    expect(html).toContain('处理已有记录 40,304 条')
    expect(html).toContain('读取 437,099 条')
    expect(html).toContain('过滤 389,920 条')
    expect(html).toContain('去重 6,875 条')
    expect(html).not.toContain('入库 0 条')
  })

  it('五类运行记录的列表分别展示输入量、处理结果和撤回实绩', async () => {
    const common = {
      status: 'succeeded', stage: 'succeeded', progress: 100,
      created_at: '2026-09-25T09:00:00+08:00',
    }
    const html = await renderComponent(CollectionRuntimeTable, {
      items: [
        {
          ...common, record_id: 'import-1', record_type: 'excel_import', display_name: '单文件导入',
          import_stats: {
            rows_seen: 5, rows_matched: 3, rows_filtered_out: 2,
            duplicates_removed: 1, rows_ingested: 2, rows_rejected: 0,
          },
        },
        {
          ...common, record_id: 'campaign-1', record_type: 'data_import_campaign',
          display_name: '第四次导入', status: 'cancelled', stage: 'revoked',
          revocation_recomputed_content_count: 5747,
          import_stats: {
            rows_seen: 66139, rows_matched: 0, rows_filtered_out: 66139,
            duplicates_removed: 0, rows_ingested: 0, rows_rejected: 0,
          },
        },
        {
          ...common, record_id: 'discovery-1', record_type: 'tikhub_discovery',
          display_name: '主动发现', collection_stats: {
            requested_count: 12, succeeded_count: 10, failed_count: 2,
            content_count: 7, comment_count: 4, filtered_count: 3,
          },
        },
        {
          ...common, record_id: 'supplement-1', record_type: 'tikhub_batch_supplement',
          display_name: '辅助补采', collection_stats: {
            requested_count: 3, succeeded_count: 3, failed_count: 0,
            content_count: 2, comment_count: 5, filtered_count: 1,
          },
        },
      ],
      loading: false,
      error: null,
    })

    expect(html).toContain('读取 5 行 · 匹配 3 行')
    expect(html).toContain('过滤 2 行 · 重复 1 行')
    expect(html).toContain('本次处理 2 行')
    expect(html).toContain('读取 66,139 行')
    expect(html).toContain('过滤 66,139 行')
    expect(html).toContain('新建/补空/更新 0 行')
    expect(html).toContain('撤销已重组 5,747 个内容')
    expect(html).toContain('请求 12 · 成功 10 · 失败 2')
    expect(html).toContain('内容（按范围累计）7 · 评论（按范围累计）4')
    expect(html).toContain('品牌车型过滤 3')
    expect(html).toContain('请求 3 · 成功 3 · 失败 0')
    expect(html).toContain('内容（按范围累计）2 · 评论（按范围累计）5')
    expect(html).toContain('品牌车型过滤 1')
  })

  it('旧版撤销预估为零时，详情展示已提交的实际重组量', async () => {
    const html = await renderComponent(DataImportDialog, { modelValue: true }, (pinia) => {
      const store = useImportBatchesStore(pinia)
      store.selectedHistoricalCampaign = {
        id: 'campaign-4', status: 'revoked', source_kind: 'local_upload',
        ingestion_policy: 'standard_observation', root_relative_path: 'fourth.xlsx',
        created_at: '2026-09-25T09:35:55+08:00', total_rows: 66139,
        discovered_file_count: 1, ready_item_count: 1, recursive: false, can_start: false,
        progress: {
          preflight_completed_file_count: 1, preflight_percent: 100,
          migration_completed_row_count: 66139, migration_percent: 100,
        },
        stats: { filtered: 66139 },
      }
      store.historicalRevocationPreview = {
        campaign_id: 'campaign-4', already_revoked: true, eligible: false,
        status: 'succeeded', recomputed_content_count: 5747,
        impact: {
          affected_content_count: 0, hidden_content_count: 0,
          retained_shared_content_count: 0, unreversible_content_count: 0,
        },
      }
    })

    expect(html).toContain('实际重组内容')
    expect(html).toContain('5747')
    expect(html).toContain('创建撤销时的影响预估与后台实际处理量不一致')
    expect(html).not.toContain('受影响内容<b>0</b>')
  })

  it('运行记录覆盖 Loading、Empty 和 Error/Retry 正式状态', async () => {
    const loadingHtml = await renderComponent(CollectionRuntimeTable, {
      items: [], loading: true, error: null,
    })
    const emptyHtml = await renderComponent(CollectionRuntimeTable, {
      items: [], loading: false, error: null,
    })
    const errorHtml = await renderComponent(CollectionRuntimeTable, {
      items: [], loading: false, error: 'network failed',
    })

    expect(loadingHtml).toContain('正在读取采集运行…')
    expect(loadingHtml.match(/skeleton-row/g)).toHaveLength(3)
    expect(emptyHtml).toContain('暂无采集运行')
    expect(emptyHtml).toContain('可导入数据，或创建一次辅助补采任务。')
    expect(errorHtml).toContain('采集运行加载失败，请稍后重试。')
    expect(errorHtml).toContain('重试')
  })

  it('导入和补采详情把内部 ID、错误码与后台任务信息下沉到技术详情', async () => {
    const [importSource, runSource] = await Promise.all([
      readCollectionRuntimeSource('components/ImportBatchDetailDrawer.vue'),
      readCollectionRuntimeSource('components/CollectionRunDetailDrawer.vue'),
    ])

    expect(importSource).toContain('label="批次详情"')
    expect(importSource).toContain("label: '运行概览'")
    expect(importSource).toContain("label: '执行进度'")
    expect(importSource).toContain("label: '任务信息'")
    expect(importSource).toContain("label: '问题记录'")
    expect(importSource).toContain('<summary>技术详情</summary>')
    expect(importSource).toContain('导入 ID')
    expect(importSource).not.toContain('后台任务状态')
    expect(importSource).not.toContain('上传与 Artifact')
    expect(runSource).toContain('label="辅助补采运行详情"')
    expect(runSource).toContain('<summary>技术详情</summary>')
    expect(runSource).toContain('运行 ID')
    expect(runSource).not.toContain('TikHub 运行详情')
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

  it('辅助补采文案保持产品化，平台和搜索配置继续由 Capability 动态驱动', async () => {
    const [drawerSource, pageSource] = await Promise.all([
      readCollectionRuntimeSource('components/TikHubSupplementDrawer.vue'),
      readCollectionRuntimeSource('CollectionRuntimePage.vue'),
    ])

    expect(drawerSource).toContain('label="新建辅助补采"')
    expect(drawerSource).toContain('searchCapability(platform)')
    expect(drawerSource).toContain('availablePlatforms')
    expect(drawerSource).not.toContain('aria-label="新建 TikHub 辅助补采"')
    expect(pageSource).not.toContain('TikHub Collection Run / Job 已创建')
    expect(pageSource).not.toContain('Worker 在后台执行')
  })
})
