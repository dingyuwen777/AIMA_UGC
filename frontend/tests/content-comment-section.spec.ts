import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import type { ContentCommentResponse } from '../src/generated/api/client'
import ContentCommentSection from '../src/features/voice-plaza/pages/VoicePlazaPage/components/ContentCommentSection.vue'

const root = {
  id: '01991f80-6d5d-7dc8-95cb-c67c12345670',
  external_comment_id: 'root-1',
  root_comment_id: 'root-1',
  parent_comment_id: null,
  parent_author_display_name: null,
  author_display_name: '蜂蜜柚子',
  text: '那个，异地行么',
  published_at: '2026-09-12T20:00:00+08:00',
  like_count: 1,
  reply_count: 2,
  ingested_reply_count: 2,
  is_by_content_author: false,
}

async function render(replies: Record<string, ContentCommentResponse[]>): Promise<string> {
  return renderToString(createSSRApp({
    render: () => h(ContentCommentSection, {
      roots: [root],
      replies,
      replyStates: {
        'root-1': {
          loaded: true,
          loading: false,
          error: null,
          nextCursor: null,
          hasMore: false,
          totalCount: replies['root-1']?.length ?? 0,
        },
      },
      loading: false,
      loadingNext: false,
      error: null,
      hasMore: false,
      rootTotalCount: 1,
      ingestedTotalCount: 3,
      providerTotalCount: 4,
      coverage: 'partial',
    }),
  }))
}

async function renderEmpty(providerTotalCount: number | null): Promise<string> {
  return renderToString(createSSRApp({
    render: () => h(ContentCommentSection, {
      roots: [],
      replies: {},
      replyStates: {},
      loading: false,
      loadingNext: false,
      error: null,
      hasMore: false,
      rootTotalCount: 0,
      ingestedTotalCount: 0,
      providerTotalCount,
      coverage: null,
    }),
  }))
}

describe('content comment section', () => {
  it('用缩进线程和自然语言回复对象展示直接父子关系', async () => {
    const html = await render({
      'root-1': [
        {
          id: '01991f80-6d5d-7dc8-95cb-c67c12345671',
          external_comment_id: 'reply-1',
          root_comment_id: 'root-1',
          parent_comment_id: 'root-1',
          parent_author_display_name: '蜂蜜柚子',
          author_display_name: '诗和远方',
          text: '不异地哦哥',
          published_at: '2026-09-12T20:05:00+08:00',
          ingested_reply_count: 0,
          is_by_content_author: true,
        },
        {
          id: '01991f80-6d5d-7dc8-95cb-c67c12345672',
          external_comment_id: 'reply-2',
          root_comment_id: 'root-1',
          parent_comment_id: null,
          parent_author_display_name: null,
          author_display_name: '平台用户',
          text: '只知道属于这个一级评论',
          ingested_reply_count: 0,
        },
      ],
    })

    expect(html).toContain('蜂蜜柚子')
    expect(html).toContain('诗和远方')
    expect(html).toContain('回复 蜂蜜柚子')
    expect(html).toContain('属于该一级评论线程')
    expect(html).not.toContain('回复这条一级评论')
    expect(html).toContain('原作者')
    expect(html).toContain('平台记录')
    expect(html).toContain('已采集')
    expect(html).toContain('当前显示')
    expect(html).not.toContain('root_comment_id')
    expect(html).not.toContain('parent_comment_id')
  })

  it('未进行辅助补采时以中性状态提示评论尚未采集', async () => {
    const html = await renderEmpty(42)

    expect(html).toContain('评论尚未采集')
    expect(html).toContain('当前数据记录显示 42 条评论')
    expect(html).toContain('本地尚未采集评论正文')
    expect(html).toContain('采集运行中心')
    expect(html).not.toContain('评论暂时加载失败')
  })

  it('数据记录本身没有评论时不误报为采集失败', async () => {
    const html = await renderEmpty(0)

    expect(html).toContain('数据记录中暂无评论')
    expect(html).toContain('当前数据记录的评论数为 0')
    expect(html).toContain('这不是采集异常')
    expect(html).not.toContain('评论尚未采集')
  })
})
