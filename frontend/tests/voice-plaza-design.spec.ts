import { createPinia, type Pinia } from 'pinia'
import { createSSRApp, h, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import type { AnalysisContentRunResponse } from '../src/generated/api/client'
import VoicePlazaPage from '../src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue'
import VoicePlazaTable from '../src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaTable.vue'
import { useVoicePlazaStore } from '../src/features/voice-plaza/store'

const blankRoute = { render: () => h('div') }

const baseAnalysisRun: AnalysisContentRunResponse = {
  id: '62345678-1234-5678-1234-567812345678',
  planner_job_id: '52345678-1234-5678-1234-567812345678',
  sequence_no: 8,
  status: 'running',
  run_intent: 'manual_reanalysis',
  scope: 'selected',
  target_count: 100,
  shard_count: 2,
  shard_size: 50,
  prompt_version: 'content_labeling_v3',
  prompt_sha256: 'a'.repeat(64),
  taxonomy_sha256: 'b'.repeat(64),
  model_provider: 'openai-compatible',
  model: 'fixture-model',
  generation_config: { temperature: 0 },
  generation_config_hash: 'c'.repeat(64),
  stats: { pending: 50, succeeded: 48, failed: 2, cancelled: 0, stale: 0 },
  shards: [
    {
      request_id: '63345678-1234-5678-1234-567812345678',
      job_id: '64345678-1234-5678-1234-567812345678',
      shard_no: 0,
      target_count: 50,
      status: 'succeeded',
      progress: 100,
      error_code: null,
    },
    {
      request_id: '65345678-1234-5678-1234-567812345678',
      job_id: '66345678-1234-5678-1234-567812345678',
      shard_no: 1,
      target_count: 50,
      status: 'running',
      progress: 0,
      error_code: null,
    },
  ],
  created_at: '2026-09-03T18:00:00+08:00',
  started_at: '2026-09-03T18:00:05+08:00',
  finished_at: null,
}

/** 使用真实 App Shell 依赖渲染组件，并允许测试按公开 Store 状态建立页面前置条件。 */
async function renderComponent(
  component: Component,
  props: Record<string, unknown> = {},
  prepare?: (pinia: Pinia) => void,
): Promise<string> {
  const app = createSSRApp({ render: () => h(component, props) })
  const pinia = createPinia()
  app.use(pinia)
  prepare?.(pinia)
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
  await router.push('/voice-plaza')
  await router.isReady()
  return renderToString(app)
}

describe('声音广场正式 Figma 基线', () => {
  it('复用正式 App Shell、页面标题和公共按钮，而不是继续维护页面私有标题动作', async () => {
    const html = await renderComponent(VoicePlazaPage)

    expect(html).toContain('class="aima-page-header"')
    expect(html.match(/class="aima-button/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
    expect(html).toContain('浏览全部渠道入库的用户声音，查看 AI 情感与完整标签结果')
    expect(html).not.toContain('>↻ 刷新<')
    expect(html).not.toContain('>◇ AI 打标<')
    expect(html).not.toContain('>⇩ 导出记录<')
  })

  it('筛选区保留业务字段，但不向用户暴露内部来源 UUID 输入框', async () => {
    const html = await renderComponent(VoicePlazaPage)

    for (const label of [
      '搜索内容',
      '平台',
      'AI 相关性',
      '发声类型',
      'AI 情感',
      'AI 状态',
      '内容类型',
      '一级标签',
      '二级标签',
      '发布开始',
      '发布结束',
    ]) expect(html).toContain(label)

    expect(html).not.toContain('来源 Batch / Run ID')
    expect(html).not.toContain('UUID / 来源标识')
    expect(html).toContain('分类来自当前发布的 Analysis Scheme')
    expect(html).toContain('车型来自版本化目录')
    expect(html).toContain('歧义别名不会自动选择')
  })

  it('终态 Analysis Run 不再作为历史大卡片占据声音广场正文', async () => {
    const terminalRun: AnalysisContentRunResponse = {
      ...baseAnalysisRun,
      sequence_no: 9,
      status: 'succeeded',
      stats: { pending: 0, succeeded: 98, failed: 2, cancelled: 0, stale: 0 },
      finished_at: '2026-09-03T18:05:00+08:00',
    }
    const html = await renderComponent(VoicePlazaPage, {}, (pinia) => {
      useVoicePlazaStore(pinia).analysisRuns = [terminalRun]
    })

    expect(html).not.toContain('AI Analysis Run 历史')
    expect(html).not.toContain('Run #9')
  })

  it('仅对活动 Analysis Run 展示紧凑状态，并提供进入全局任务中心的入口', async () => {
    const html = await renderComponent(VoicePlazaPage, {}, (pinia) => {
      useVoicePlazaStore(pinia).analysisRuns = [baseAnalysisRun]
    })

    expect(html).toContain('AI 打标任务')
    expect(html).toContain('Run #8 · 处理中')
    expect(html).toContain('50 / 100 条已取得终态')
    expect(html).toContain('查看任务中心')
    expect(html).not.toContain('AI Analysis Run 历史')
  })

  it('Empty 与 Error 使用正式状态文案，不虚构分页结果', async () => {
    const empty = await renderComponent(VoicePlazaTable, {
      items: [],
      loading: false,
      error: null,
      selectedIds: [],
      reviewing: false,
    })
    const error = await renderComponent(VoicePlazaTable, {
      items: [],
      loading: false,
      error: 'connection refused',
      selectedIds: [],
      reviewing: false,
    })

    expect(empty).toContain('暂无符合条件的内容')
    expect(empty).toContain('当前没有可加载的下一页，不显示虚构页码')
    expect(empty).toContain('data-aima-icon="empty"')
    expect(error).toContain('暂时无法加载声音记录')
    expect(error).toContain('检查网络或服务状态后点击“刷新数据”重试')
  })
})
