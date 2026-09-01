import { createPinia } from 'pinia'
import { createSSRApp, h, type Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import VoicePlazaPage from '../src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue'
import VoicePlazaTable from '../src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaTable.vue'

const blankRoute = { render: () => h('div') }

/** 使用真实 App Shell 依赖渲染组件，验证正式 Figma 基线的稳定结构。 */
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

  it('筛选区保留真实字段并明确示例不是服务器事实', async () => {
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
      '来源 Batch / Run ID',
      '发布开始',
      '发布结束',
    ]) expect(html).toContain(label)

    expect(html).toContain('分类选项来自 GET /api/v1/content-analysis-taxonomy')
    expect(html).toContain('查询字段来自 GET /api/v1/contents')
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
