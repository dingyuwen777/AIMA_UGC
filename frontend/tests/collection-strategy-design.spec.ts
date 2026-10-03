import { createSSRApp, h, type Component } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'
import { createPinia } from 'pinia'

import type {
  CollectionPlanResponse,
} from '../src/generated/api/client'
import TikHubPlanDialog from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/TikHubPlanDialog.vue'
import PlanPanel from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/PlanPanel.vue'
import StrategyKpiCards from '../src/features/collection-strategy/pages/CollectionStrategyPage/components/StrategyKpiCards.vue'
import { formatBeijingDateTime } from '../src/features/collection-strategy/presentation'

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
  comment_policy: 'adaptive', plan_type: 'tikhub',
  platforms: [{ platform: 'xiaohongshu', provider_config_id: 'provider-1', search_config: {} }],
  keyword_pack_ids: ['pack-1', 'pack-2'],
  brand_ids: ['brand-1', 'brand-2'],
  created_at: '2026-08-28T08:00:00+08:00',
  updated_at: '2026-08-28T08:00:00+08:00',
}

async function renderComponent(component: Component, props: Record<string, unknown>): Promise<string> {
  const context: { teleports?: Record<string, string> } = {}
  const app = createSSRApp({ render: () => h(component, props) })
  app.use(createPinia())
  const html = await renderToString(app, context)
  return html + Object.values(context.teleports ?? {}).join('')
}

describe('采集策略正式 Figma 组件基线', () => {
  it('把 API 绝对时间固定转换为 Figma 约定的北京时间分钟粒度', () => {
    expect(formatBeijingDateTime('2026-08-28T00:00:00Z')).toBe('2026/8/28 08:00')
  })

  it('使用三个独立动态指标卡并展示正式中文业务值', async () => {
    const html = await renderComponent(StrategyKpiCards, {
      packCount: 12,
      brandCount: 3,
      enabledPlanCount: 4,
      loading: false,
    })

    expect(html.match(/class="strategy-summary"/g)).toHaveLength(1)
    expect(html.match(/class="summary-item/g)).toHaveLength(3)
    expect(html).toContain('关键词包')
    expect(html).toContain('启用品牌')
    expect(html).toContain('>3 个品牌<')
    expect(html).toContain('启用计划')
    expect(html).not.toContain('Discovery')
  })

  it('计划列表展示通用七列和显式类型、策略，不暴露机器身份', async () => {
    const html = await renderComponent(PlanPanel, {
      plans: [plan],
      packs: [
        { id: 'pack-1', name: '新品词包', description: '', enabled: true, version: 3, keyword_count: 2 },
        { id: 'pack-2', name: '次要词包', description: '', enabled: true, version: 1, keyword_count: 1 },
      ],
      brands: [
        { id: 'brand-1', code: 'AIMA', display_name: '爱玛', role: 'owned', status: 'active', version: 1, catalog_version: 8, aliases: [], created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z' },
        { id: 'brand-2', code: 'YADEA', display_name: '雅迪', role: 'competitor', status: 'active', version: 1, catalog_version: 8, aliases: [], created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z' },
      ],
      total: 1,
      offset: 0,
      limit: 20,
      loading: false,
      saving: false,
      toggleReason: () => null,
    })

    expect(html.match(/<th[ >]/g)).toHaveLength(7)
    expect(html).not.toContain('>采集策略</th>')
    expect(html).toMatch(/<th[^>]*>计划名称<\/th>/)
    expect(html).toContain('采集范围')
    expect(html).toContain('计划类型')
    expect(html).toContain('TikHub')
    expect(html).toContain('评论策略')
    expect(html).toContain('自适应采集')
    expect(html).not.toMatch(/<th[^>]*>目标平台<\/th>/)
    expect(html).not.toContain('目标平台 / 采集渠道')
    expect(html).toContain('2 个关键词包 · 1 个平台')
    expect(html).toContain('新品词包')
    expect(html).toContain('品牌：爱玛')
    expect(html).toContain('另有 2 项条件')
    expect(html).not.toContain('次要词包')
    expect(html).not.toContain('TikHub 主配置')
    expect(html).not.toContain('计划编号：')
    expect(html).not.toContain('33333333-3333-4333-8333-333333333333')
    expect(html).toContain('每6小时')
  })

  it('TikHub弹窗复用视口约束，保留五个频率预设并说明两种策略', async () => {
    const html = await renderComponent(TikHubPlanDialog, {
      modelValue: true,
      initialPlan: plan,
      packs: [],
      packDetails: {},
      capabilities: null,
      saving: false,
      loadingPackDetails: false,
      'onUpdate:modelValue': () => undefined,
    })

    expect(html).toContain('编辑采集计划')
    expect(html).toContain('通过 TikHub 按关键词持续发现并采集内容')
    expect(html).toContain('搜索条件 · 关键词包')
    expect(html).toContain('内容过滤 · 品牌')
    expect(html).toContain('目标平台')
    expect(html).toContain('评论采集策略')
    expect(html).toContain('全量采集')
    expect(html).toContain('50 条')
    expect(html).toContain('5 条')
    expect(html).toContain('100 页安全上限')
    expect(html).toContain('没有请求预算或金额上限')
    expect(html).toContain('width:min(960px, calc(100vw - 48px))')
    expect(html).toContain('height:min(820px, calc(100dvh - 48px))')
    expect(html).toContain('aria-label="执行频率"')
    expect(html).toMatch(/<option value="0 \*\/6 \* \* \*"[^>]* selected>每6小时<\/option>/)
    for (const [label, value] of [
      ['每1小时', '0 * * * *'],
      ['每3小时', '0 */3 * * *'],
      ['每6小时', '0 */6 * * *'],
      ['每12小时', '0 */12 * * *'],
      ['每天 00:00', '0 0 * * *'],
    ]) {
      expect(html).toContain(`value="${value}"`)
      expect(html).toContain(`>${label}</option>`)
    }
  })

  it('共用新建弹窗默认网站计划，显示名称频率品牌并隐藏 TikHub 专有配置', async () => {
    const html = await renderComponent(TikHubPlanDialog, {
      modelValue: true, packs: [], packDetails: {}, capabilities: null,
      saving: false, loadingPackDetails: false,
    })
    expect(html).toContain('新建采集计划')
    expect(html).toMatch(/<input checked type="radio" value="wisersone"/)
    expect(html).toContain('WisersOne 网站下载')
    expect(html).toContain('计划名称')
    expect(html).toContain('执行频率')
    expect(html).toContain('内容过滤 · 品牌')
    expect(html).toContain('下载过去 24 小时')
    expect(html).toContain('width:min(960px, calc(100vw - 48px))')
    expect(html).not.toContain('搜索条件 · 关键词包')
    expect(html).not.toContain('评论采集策略')
    expect(html).not.toContain('目标平台')
  })
})
