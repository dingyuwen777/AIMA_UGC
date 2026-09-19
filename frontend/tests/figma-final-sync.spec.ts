import { renderToString } from '@vue/server-renderer'
import { shallowMount } from '@vue/test-utils'
import { createSSRApp, h, nextTick } from 'vue'
import { describe, expect, it } from 'vitest'

import type { ContentDetailResponse } from '../src/generated/api/client'
import AdminConfigurationPage from '../src/features/admin-configuration/pages/AdminConfigurationPage.vue'
import CatalogConfigurationPanel from '../src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue'
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
    collect_count: 0,
    view_count: 0,
    follower_count: 0,
  },
  analysis: {
    status: 'pending',
    relevance: null,
    sentiment: null,
    voice_type: null,
    labels: [],
    manual_locked_dimensions: [],
  },
  comment_coverage: null,
  availability: null,
  source: { provider_name: 'tikhub' },
} as unknown as ContentDetailResponse

describe('Figma 与前端最终交互同步', () => {
  it('详情抽屉提供与正式 Figma 一致的四段快捷导航', async () => {
    const app = createSSRApp({
      render: () => h(ContentDetailDrawer, {
        modelValue: true,
        item: detail,
        loading: false,
      }),
    })
    const html = await renderToString(app)

    expect(html).toContain('aria-label="详情快捷导航"')
    for (const label of ['内容', 'AI 信息', '人工确认', '评论']) {
      expect(html).toContain(`>${label}<`)
    }
  })

  it('当前管理页有未保存修改时不会直接切换到其它 Tab', async () => {
    const wrapper = shallowMount(AdminConfigurationPage)
    const catalog = wrapper.findComponent(CatalogConfigurationPanel)

    catalog.vm.$emit('dirty-change', true)
    await nextTick()

    const target = wrapper.findAll('button').find((button) => button.text() === 'TikHub')
    expect(target).toBeDefined()
    await target!.trigger('click')
    await nextTick()

    const current = wrapper.findAll('button').find((button) => button.text() === '品牌与车型')
    expect(current?.classes()).toContain('active')
  })
})
