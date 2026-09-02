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
  keyword_pack_ids: ['pack-1', 'pack-2'],
  vehicle_model_ids: ['vehicle-1', 'vehicle-2'],
  created_at: '2026-08-28T08:00:00+08:00',
  updated_at: '2026-08-28T08:00:00+08:00',
}

async function renderComponent(component: Component, props: Record<string, unknown>): Promise<string> {
  return renderToString(createSSRApp({ render: () => h(component, props) }))
}

describe('采集策略正式 Figma 组件基线', () => {
  it('把 API 绝对时间固定转换为 Figma 约定的北京时间分钟粒度', () => {
    expect(formatBeijingDateTime('2026-08-28T00:00:00Z')).toBe('2026/8/28 08:00')
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

  it('计划列表只保留六列，并像 Figma 一样优先各展示一个词包和车型后汇总剩余范围', async () => {
    const html = await renderComponent(PlanPanel, {
      plans: [plan],
      packs: [
        { id: 'pack-1', name: '新品词包', description: '', enabled: true, version: 3, keyword_count: 2 },
        { id: 'pack-2', name: '次要词包', description: '', enabled: true, version: 1, keyword_count: 1 },
      ],
      vehicles: [
        {
          id: 'vehicle-1', code: 'A7', display_name: '爱玛 A7', status: 'deprecated', version: 2,
          catalog_version: 8, merged_into_id: null, aliases: [], keyword_pack_ids: [], referenced: true,
          created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z',
        },
        {
          id: 'vehicle-2', code: 'B9', display_name: '爱玛 B9', status: 'active', version: 1,
          catalog_version: 8, merged_into_id: null, aliases: [], keyword_pack_ids: [], referenced: false,
          created_at: '2026-08-01T00:00:00Z', updated_at: '2026-08-28T00:00:00Z',
        },
      ],
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
    expect(html).toContain('词包 / 车型')
    expect(html).toContain('目标平台 / 采集渠道')
    expect(html).toContain('新品词包')
    expect(html).toContain('车型：爱玛 A7')
    expect(html).toContain('另有 2 项范围')
    expect(html).not.toContain('次要词包')
    expect(html).not.toContain('车型：爱玛 B9')
    expect(html).toContain('计划编号： 33333333-3333-4333-8333-333333333333')
    expect(html).toContain('每6小时')
  })

  it('新建计划只提供 Figma 批准的五个频率预设且默认每六小时', async () => {
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

    expect(html).toContain('保存发现范围与周期采集配置')
    expect(html).toContain('4. 目标平台与采集渠道')
    expect(html).toContain('5. 执行频率')
    expect(html).toContain('系统固定规则')
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
})
