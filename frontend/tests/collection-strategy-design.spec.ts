import { createSSRApp, h, type Component } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'

import type {
  CollectionPlanResponse,
  GlobalRelevanceConfigResponse,
} from '../src/generated/api/client'
import PlanCreateDrawer from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/PlanCreateDrawer.vue'
import PlanPanel from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/PlanPanel.vue'
import StrategyKpiCards from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/StrategyKpiCards.vue'
import { formatBeijingDateTime } from '../src/features/collection-strategy/presentation'

const relevance: GlobalRelevanceConfigResponse = {
  keyword_pack_id: 'pack-1',
  keyword_pack_version: 3,
  version: 2,
  effective_keywords: ['爱玛'],
  updated_at: '2026-08-28T08:00:00+08:00',
}

const plan: CollectionPlanResponse = {
  id: '33333333-3333-4333-8333-333333333333',
  name: '新品口碑采集',
  enabled: true,
  schedule_expr: '0 */6 * * *',
  timezone: 'Asia/Shanghai',
  schedule_version: 2,
  next_run_at: null,
  last_scheduled_at: null,
  detail_policy: 'on_change',
  comment_policy: 'adaptive',
  platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1', search_config: {} }],
  keyword_pack_ids: ['pack-1'],
  created_at: '2026-08-28T08:00:00+08:00',
  updated_at: '2026-08-28T08:00:00+08:00',
}

async function renderComponent(component: Component, props: Record<string, unknown>): Promise<string> {
  return renderToString(createSSRApp({ render: () => h(component, props) }))
}

describe('采集策略正式 Figma 组件基线', () => {
  it('把 API 绝对时间固定转换为北京时间而不依赖浏览器宿主时区', () => {
    expect(formatBeijingDateTime('2026-08-28T00:00:00Z')).toBe('2026/8/28 08:00:00')
  })

  it('将三个动态指标放在一个摘要条中并使用正式中文术语', async () => {
    const html = await renderComponent(StrategyKpiCards, {
      packCount: 12,
      relevance,
      enabledPlanCount: 4,
      relevancePackName: '品牌核心相关词',
      loading: false,
    })

    expect(html.match(/class="strategy-summary"/g)).toHaveLength(1)
    expect(html.match(/class="summary-item/g)).toHaveLength(3)
    expect(html).toContain('关键词包')
    expect(html).toContain('品牌核心相关词')
    expect(html).not.toContain('Discovery')
  })

  it('计划列表只保留六个有信息增量的列并展示可读周期', async () => {
    const html = await renderComponent(PlanPanel, {
      plans: [plan],
      packs: [{ id: 'pack-1', name: '新品词包', description: '', enabled: true, version: 3, keyword_count: 2 }],
      providers: [{ id: 'provider-1', provider: 'tikhub', display_name: 'TikHub 主配置' }],
      total: 1,
      offset: 0,
      limit: 20,
      loading: false,
      saving: false,
      toggleReason: () => null,
    })

    expect(html.match(/<th[ >]/g)).toHaveLength(6)
    expect(html).not.toContain('>采集策略</th>')
    expect(html).toContain('计划 / 编号')
    expect(html).toContain('目标平台 / 采集渠道')
    expect(html).toContain('每 6 小时')
  })

  it('新建计划只提供 Figma 批准的五个周期预设且默认每六小时', async () => {
    const html = await renderComponent(PlanCreateDrawer, {
      modelValue: true,
      packs: [],
      packDetails: {},
      capabilities: null,
      relevanceName: '',
      relevanceAvailable: false,
      saving: false,
      loadingPackDetails: false,
      'onUpdate:modelValue': () => undefined,
    })

    expect(html).toContain('aria-label="执行周期"')
    expect(html).toMatch(/<option value="0 \*\/6 \* \* \*"[^>]* selected>每 6 小时<\/option>/)
    for (const [label, value] of [
      ['每 1 小时', '0 * * * *'],
      ['每 3 小时', '0 */3 * * *'],
      ['每 6 小时', '0 */6 * * *'],
      ['每 12 小时', '0 */12 * * *'],
      ['每天 00:00', '0 0 * * *'],
    ]) {
      expect(html).toContain(`value="${value}"`)
      expect(html).toContain(`>${label}</option>`)
    }
  })
})
