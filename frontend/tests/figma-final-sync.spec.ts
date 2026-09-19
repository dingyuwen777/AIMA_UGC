import { readFile } from 'node:fs/promises'

import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { describe, expect, it } from 'vitest'

import type { ContentDetailResponse } from '../src/generated/api/client'
import ContentDetailDrawer from '../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentDetailDrawer.vue'

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

/** 使用仓库现有 SSR 测试模式检查静态结构；点击行为由 Playwright Browser Journey 单独验收。 */
async function renderDetail(): Promise<string> {
  const app = createSSRApp({
    render: () => h(ContentDetailDrawer, {
      modelValue: true,
      item: detail,
      loading: false,
    }),
  })
  return renderToString(app)
}

describe('Figma 与前端最终交互同步', () => {
  it('详情抽屉提供与正式 Figma 一致的四段快捷导航', async () => {
    const html = await renderDetail()

    expect(html).toContain('aria-label="详情快捷导航"')
    for (const label of ['内容', 'AI 信息', '人工确认', '评论']) {
      expect(html).toContain(`>${label}</button>`)
    }
  })

  it('管理员页由 Page Owner 统一拦截未保存草稿的 Tab 切换', async () => {
    const source = await readFile(
      new URL(
        '../src/features/admin-configuration/pages/AdminConfigurationPage.vue',
        import.meta.url,
      ),
      'utf8',
    )

    expect(source).toContain('@click="requestTab(item[0])"')
    expect(source).toContain('if (currentDirty.value)')
    expect(source).toContain('pendingTab.value = next')
    expect(source).toContain('放弃未保存的修改？')
    expect(source).toContain('继续编辑')
    expect(source).toContain('放弃修改并切换')
  })
})
