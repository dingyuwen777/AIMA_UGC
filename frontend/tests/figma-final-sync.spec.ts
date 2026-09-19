import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { createSSRApp, defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'

import type { ContentDetailResponse } from '../src/generated/api/client'
import AdminConfigurationPage from '../src/features/admin-configuration/pages/AdminConfigurationPage.vue'
import { useIdentityStore } from '../src/features/identity/store'
import ContentDetailDrawer from '../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue'

type RenderContext = NonNullable<Parameters<typeof renderToString>[1]> & {
  teleports?: Record<string, string>
}

const detail = {
  id: 'content-final-sync',
  platform: 'xiaohongshu',
  author_display_name: '演示用户',
  published_at: '2026-09-19T10:00:00+08:00',
  title: '详情导航验收',
  text: '用于验证详情抽屉分区导航。',
  content_type: 'note',
  content_url: null,
  media: [],
  supplement_status: null,
  brands: [],
  vehicles: [],
  competition_scope: 'none_detected',
  metrics: {
    like_count: 0,
    comment_count: 0,
    share_count: 0,
    repost_count: null,
    favorite_count: 0,
    play_count: null,
    view_count: 0,
  },
  analysis: {
    status: 'pending',
    relevance: null,
    sentiment: null,
    voice_type: null,
    labels: [],
    manual_locked_dimensions: [],
  },
  effective_relevance: 'relevant',
  relevance_source: 'ai',
  comment_coverage: null,
  availability: null,
  source: { provider_name: 'tikhub' },
} as unknown as ContentDetailResponse

/** SSR 下 Teleport 内容位于 context.teleports；合并后按用户可见结构断言。 */
async function renderWithTeleports(app: ReturnType<typeof createSSRApp>): Promise<string> {
  const context = {} as RenderContext
  const html = await renderToString(app, context)
  return [html, ...Object.values(context.teleports ?? {})].join('')
}

/** 复用仓库现有管理员 SSR 测试基线，不为两个交互测试引入 DOM 仿真依赖。 */
async function renderAdminPage(): Promise<string> {
  const app = createSSRApp({ render: () => h(AdminConfigurationPage) })
  const pinia = createPinia()
  app.use(pinia)
  useIdentityStore(pinia).principal = {
    principal_id: 'local-administrator',
    display_name: '本地管理员',
    role: 'administrator',
    source: 'development',
    is_administrator: true,
  }
  app.component(
    'RouterLink',
    defineComponent({
      props: { to: { type: String, required: true } },
      setup(props, { slots }) {
        return () => h('a', { href: props.to }, slots.default?.())
      },
    }),
  )
  return renderWithTeleports(app)
}

describe('Figma 与前端最终交互同步', () => {
  it('详情抽屉提供与正式 Figma 一致的四段快捷导航结构', async () => {
    const app = createSSRApp({
      render: () => h(ContentDetailDrawer, {
        modelValue: true,
        item: detail,
        loading: false,
      }),
    })
    const html = await renderWithTeleports(app)

    expect(html).toContain('aria-label="详情快捷导航"')
    for (const label of ['内容', 'AI 信息', '人工确认', '评论']) {
      expect(html).toContain(`>${label}<`)
    }
  })

  it('管理员页面包含正式未保存切换确认结构', async () => {
    const html = await renderAdminPage()

    expect(html).toContain('放弃未保存的修改？')
    expect(html).toContain('继续编辑')
    expect(html).toContain('放弃修改并切换')
  })
})
