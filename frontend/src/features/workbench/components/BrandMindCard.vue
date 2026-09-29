<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  WorkbenchMindDimensionResponse,
  WorkbenchMindResponse,
} from '../../../generated/api/client'
import type { WorkbenchMindMetric } from '../store'

const props = defineProps<{
  mind: WorkbenchMindResponse | null
  selectedLabel: string | null
  metric: WorkbenchMindMetric
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  select: [primaryLabel: string]
  metric: [value: WorkbenchMindMetric]
  retry: []
  openVoice: [primaryLabel: string]
}>()

const dimensions = computed(() => props.mind?.dimensions ?? [])
const preparing = computed(() => props.mind?.snapshot_status === 'preparing'
  || (props.mind?.snapshot_status === 'failed' && !props.mind.computed_at))
const selected = computed(() =>
  dimensions.value.find((item) => item.primary_label === props.selectedLabel)
    ?? dimensions.value[0]
    ?? null,
)
const chartElement = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

/** 根据当前切换维度返回条形图值；占比与正向率都以 0..1 Contract 展示。 */
function metricValue(item: WorkbenchMindDimensionResponse): number {
  return props.metric === 'share' ? item.user_share : item.positive_rate ?? 0
}

/** 将比例格式化为百分数，缺失正向率明确显示“—”。 */
function percent(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2).replace(/\.0$/, '')}%`
}

/** pp 变化使用带符号格式，0 保持中性。 */
function changeText(value: number | null | undefined): string {
  if (value == null) return '较上期 —'
  const sign = value > 0 ? '+' : ''
  return `较上期 ${sign}${value.toFixed(2)}pp`
}

/** 切换用户占比/正向率只改变当前卡片表现层，不改变查询口径。 */
function setMetric(value: WorkbenchMindMetric): void {
  emit('metric', value)
}

/** active Taxonomy 的每个业务一级标签对应一条雷达轴，数量变化时自然形成 N 边图。 */
function renderChart(): void {
  if (!chartElement.value || dimensions.value.length === 0) return
  if (!chart) {
    chart = echarts.init(chartElement.value)
    chart.on('click', (event) => {
      if (event.componentType !== 'radar') return
      const label = String(event.name ?? '')
      if (dimensions.value.some((item) => item.primary_label === label)) emit('select', label)
    })
  }
  const values = dimensions.value.map(metricValue)
  const labelValues = new Map(dimensions.value.map((item) => [item.primary_label, metricValue(item)]))
  chart.setOption({
    animationDuration: 280,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#fff',
      borderColor: '#ed0b68',
      borderWidth: 1,
      textStyle: { color: '#17233d', fontSize: 11 },
      formatter: () => dimensions.value
        .map((item) => `${item.primary_label}　<b>${percent(metricValue(item))}</b>`)
        .join('<br/>'),
    },
    radar: {
      center: ['46%', '52%'],
      radius: dimensions.value.length > 8 ? '56%' : '62%',
      shape: 'polygon',
      splitNumber: 4,
      startAngle: 90,
      indicator: dimensions.value.map((item) => ({ name: item.primary_label, max: 1 })),
      axisNameGap: 12,
      axisName: {
        color: '#17233d',
        fontSize: dimensions.value.length > 8 ? 9 : 10,
        fontWeight: 600,
        lineHeight: 16,
        formatter: (name: string) => (
          `${name}\n{value|${percent(labelValues.get(name))}} {unit|${props.metric === 'share' ? '占比' : '正向率'}}`
        ),
        rich: {
          value: { color: '#ed0b68', fontSize: 14, fontWeight: 700, lineHeight: 20 },
          unit: { color: '#8a96ad', fontSize: 9, fontWeight: 400, lineHeight: 20 },
        },
      },
      axisLine: { lineStyle: { color: '#d1d5db', width: 1 } },
      splitLine: { lineStyle: { color: '#d1d5db', width: 1 } },
      splitArea: { areaStyle: { color: ['#fff', '#fff'] } },
    },
    series: [{
      type: 'radar',
      symbol: 'circle',
      symbolSize: 7,
      lineStyle: { color: '#ed0b68', width: 2.5 },
      itemStyle: { color: '#fff', borderColor: '#ed0b68', borderWidth: 2 },
      areaStyle: { color: 'rgba(237, 11, 104, .34)' },
      data: [{ value: values }],
    }],
  }, true)
}

onMounted(async () => {
  await nextTick()
  renderChart()
  if (chartElement.value) {
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(chartElement.value)
  }
})

watch([dimensions, () => props.metric], async () => {
  await nextTick()
  renderChart()
}, { deep: true })

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <section
    class="mind-card"
    :aria-busy="loading"
  >
    <header>
      <div class="title">
        <span>◎</span>
        <div>
          <h2>品牌用户心智</h2>
          <p>基于当前 active Taxonomy，动态查看一级用户心智</p>
        </div>
      </div>
      <div class="header-actions">
        <small>当前筛选 · {{ mind ? `${mind.date_from} — ${mind.date_to}` : '近30天' }}</small>
        <div class="metric-toggle">
          <button
            type="button"
            :class="{ active: metric === 'share' }"
            @click="setMetric('share')"
          >
            心智占比
          </button>
          <button
            type="button"
            :class="{ active: metric === 'positive' }"
            @click="setMetric('positive')"
          >
            正向率
          </button>
        </div>
      </div>
    </header>

    <p
      v-if="mind?.snapshot_status === 'refreshing' || (loading && !preparing)"
      class="refresh-note"
      role="status"
    >
      后台正在更新当前筛选，以下为最近成功结果…
    </p>
    <p
      v-else-if="mind?.snapshot_status === 'failed' && mind.computed_at"
      class="refresh-note"
      role="status"
    >
      当前继续显示最近成功结果，后台会自动完成后续更新。
    </p>

    <div
      v-if="error"
      class="module-state module-state--error"
      :class="{ 'module-state--inline': dimensions.length > 0 }"
      role="alert"
    >
      <strong>品牌用户心智暂时无法更新</strong>
      <span>继续保留上次成功结果。</span>
      <button
        type="button"
        @click="emit('retry')"
      >
        重试
      </button>
    </div>
    <div
      v-if="preparing"
      class="module-state"
      role="status"
    >
      首次聚合正在后台准备，完成后会自动显示…
    </div>
    <div
      v-else-if="loading && dimensions.length === 0"
      class="module-state"
    >
      正在读取品牌用户心智…
    </div>
    <div
      v-else-if="dimensions.length === 0 && !error"
      class="module-state"
    >
      当前筛选范围暂无可统计的用户心智
    </div>

    <div
      v-else
      class="mind-body"
    >
      <div class="mind-radar">
        <div class="radar-title">
          <strong>用户心智图</strong>
          <span v-if="metric === 'share'">多标签独立统计 · 可合计&gt;100%</span>
          <span v-else>仅 relevant · 正面 / relevant</span>
        </div>
        <div class="radar-stage">
          <div
            ref="chartElement"
            class="radar-chart"
            :aria-label="`用户心智图，共 ${dimensions.length} 个一级标签`"
            :data-axis-count="dimensions.length"
          />
          <div
            class="radar-center"
            aria-hidden="true"
          >
            <strong>爱玛</strong><span>心智图</span>
          </div>
          <button
            v-if="selected"
            type="button"
            class="radar-selected-card"
            @click="emit('select', selected.primary_label)"
          >
            <strong>{{ selected.primary_label }}</strong>
            <span>{{ percent(metricValue(selected)) }} <small>{{ metric === 'share' ? '占比' : '正向率' }}</small></span>
          </button>
        </div>
        <div
          class="radar-accessible-list"
          aria-label="选择一级用户心智"
        >
          <button
            v-for="item in dimensions"
            :key="item.primary_label"
            type="button"
            :aria-pressed="selected?.primary_label === item.primary_label"
            @click="emit('select', item.primary_label)"
          >
            {{ item.primary_label }} {{ percent(metricValue(item)) }}
          </button>
        </div>
      </div>

      <div
        v-if="selected"
        class="mind-detail"
      >
        <small>当前查看 · 一级心智 · {{ metric === 'share' ? '用户占比' : '正向率' }}</small>
        <div class="detail-title">
          <h3>{{ selected.primary_label }}</h3>
          <span>{{ changeText(selected.user_share_change_pp) }}</span>
        </div>
        <div class="metric-cards">
          <div>
            <span>心智占比</span>
            <strong>{{ percent(selected.user_share) }}</strong>
          </div>
          <div>
            <span>正向率</span>
            <strong>{{ percent(selected.positive_rate) }}</strong>
          </div>
        </div>
        <div class="secondary">
          <strong>主要二级心智</strong>
          <span
            v-for="item in selected.secondary_labels.slice(0, 4)"
            :key="item.secondary_label"
          >
            {{ item.secondary_label }} · {{ item.user_count }} 人
          </span>
          <span v-if="selected.secondary_labels.length === 0">暂无二级标签用户</span>
        </div>
        <div class="change-card">
          <strong>主要变化</strong>
          <p>{{ selected.change_summary }}</p>
        </div>
        <button
          class="voice-link"
          type="button"
          @click="emit('openVoice', selected.primary_label)"
        >
          查看该心智的用户原声 →
        </button>
      </div>
    </div>

    <footer v-if="mind">
      <span>可识别用户 {{ mind.identified_user_count.toLocaleString('zh-CN') }} 人</span>
      <span>当前规则覆盖 {{ (mind.analysis_coverage_rate * 100).toFixed(1) }}%</span>
    </footer>
  </section>
</template>

<style scoped>
.mind-card { display: flex; height: 100%; min-width: 0; flex-direction: column; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); box-shadow: 0 4px 12px -2px rgb(23 35 61 / 4%), 0 1px 6px rgb(23 35 61 / 8%); }
header { display: flex; min-height: 58px; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--aima-border); }
.title { display: flex; min-width: 0; align-items: center; gap: 8px; }
.title > span { display: grid; width: 28px; height: 28px; flex: none; place-items: center; border-radius: 50%; color: var(--aima-primary); background: var(--aima-primary-soft); }
.title h2, .title p { margin: 0; }
.title h2 { color: var(--aima-text); font-size: 16px; }
.title p { margin-top: 2px; color: var(--aima-text-secondary); font-size: 11px; }
.header-actions { display: flex; flex: none; align-items: center; gap: 8px; }
.header-actions small { color: var(--aima-text-disabled); font-size: 10px; }
.metric-toggle { display: flex; padding: 2px; border-radius: 6px; background: var(--aima-surface-disabled); }
.metric-toggle button { padding: 4px 7px; border: 0; border-radius: 4px; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 10px; }
.metric-toggle .active { color: var(--aima-primary); background: var(--aima-primary-soft); font-weight: 700; }
.mind-body { display: grid; min-height: 0; flex: 1; grid-template-columns: minmax(0, 1.2fr) minmax(220px, .9fr); }
.mind-radar { display: flex; min-width: 0; min-height: 0; flex-direction: column; padding: 10px; border-right: 1px solid var(--aima-border); }
.radar-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.radar-title strong { color: var(--aima-text); font-size: 12px; }
.radar-title span { color: var(--aima-text-disabled); font-size: 9px; white-space: nowrap; }
.radar-stage { position: relative; min-height: 230px; flex: 1; overflow: hidden; }
.radar-chart { width: 100%; height: 100%; min-height: 230px; }
.radar-center { position: absolute; top: 52%; left: 46%; display: grid; width: 76px; height: 76px; place-content: center; transform: translate(-50%, -50%); border-radius: 50%; color: #fff; background: linear-gradient(145deg, #f5418b, #ed0b68); box-shadow: 0 8px 18px rgb(237 11 104 / 25%); text-align: center; pointer-events: none; }
.radar-center strong { font-size: 17px; }
.radar-center span { margin-top: 2px; font-size: 9px; }
.radar-selected-card { position: absolute; top: 12px; right: 4px; display: grid; min-width: 104px; gap: 5px; padding: 9px 12px; border: 2px solid #ed0b68; border-radius: 12px; color: var(--aima-text); background: #fff5f9; cursor: pointer; text-align: left; box-shadow: 0 4px 10px rgb(237 11 104 / 10%); }
.radar-selected-card strong { max-width: 150px; overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.radar-selected-card > span { color: #ed0b68; font-size: 16px; font-weight: 700; }
.radar-selected-card small { color: var(--aima-text-disabled); font-size: 9px; font-weight: 400; }
.radar-accessible-list { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.mind-detail { display: flex; min-width: 0; flex-direction: column; gap: 9px; padding: 12px; overflow: auto; }
.mind-detail > small { color: var(--aima-text-disabled); font-size: 9px; text-transform: uppercase; }
.detail-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.detail-title h3 { margin: 0; color: var(--aima-text); font-size: 18px; }
.detail-title span { color: var(--aima-primary); font-size: 10px; font-weight: 600; }
.metric-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.metric-cards div { display: grid; min-height: 58px; align-content: center; gap: 3px; padding: 9px 11px; border-radius: 7px; background: var(--aima-surface-disabled); }
.metric-cards span { color: var(--aima-text-disabled); font-size: 9px; }
.metric-cards strong { color: var(--aima-text); font-size: 18px; }
.secondary { display: grid; gap: 4px; }
.secondary strong { color: var(--aima-text); font-size: 10px; }
.secondary span { color: var(--aima-text-secondary); font-size: 9px; }
.change-card { padding: 10px 12px; border-left: 2px solid var(--aima-primary); border-radius: 6px; background: var(--aima-primary-soft); }
.change-card strong { color: var(--aima-text); font-size: 10px; }
.change-card p { margin: 4px 0 0; color: var(--aima-text-secondary); font-size: 9px; line-height: 15px; }
.voice-link, .module-state button { align-self: flex-start; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; font-weight: 600; }
.module-state { display: grid; min-height: 220px; place-content: center; gap: 5px; color: var(--aima-text-disabled); text-align: center; font-size: 12px; }
.module-state--error { color: var(--aima-danger); }
.module-state--error span { color: var(--aima-text-secondary); }
.module-state--inline { min-height: 0; grid-template-columns: auto auto auto; align-items: center; justify-content: start; margin: 5px 12px 0; padding: 5px 8px; border-radius: 5px; background: var(--aima-primary-soft); text-align: left; font-size: 10px; }
.refresh-note { margin: 5px 12px 0; color: var(--aima-text-secondary); font-size: 10px; }
footer { display: flex; min-height: 26px; align-items: center; justify-content: space-between; padding: 5px 12px; border-top: 1px solid var(--aima-border); color: var(--aima-text-disabled); font-size: 9px; }
@container (max-width: 760px) {
  header { align-items: flex-start; flex-wrap: wrap; }
  .header-actions { width: 100%; justify-content: space-between; }
  .mind-body { grid-template-columns: minmax(0, 1fr); overflow: auto; }
  .mind-radar { min-height: 310px; border-right: 0; border-bottom: 1px solid var(--aima-border); }
}
@container (max-width: 520px) {
  .header-actions { align-items: flex-start; flex-direction: column; }
  .radar-title { align-items: flex-start; flex-direction: column; }
  .radar-selected-card { top: 4px; right: 0; min-width: 92px; padding: 7px 9px; }
  .metric-cards { grid-template-columns: minmax(0, 1fr); }
}
</style>
