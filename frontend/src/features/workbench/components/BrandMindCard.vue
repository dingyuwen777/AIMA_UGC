<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import type {
  WorkbenchMindDimensionResponse,
  WorkbenchMindResponse,
} from '../../../generated/api/client'
import type { WorkbenchMindMetric } from '../store'
import WorkbenchDateLabel from './WorkbenchDateLabel.vue'
import { radarGeometry } from './radarGeometry'

const props = defineProps<{
  mind: WorkbenchMindResponse | null
  selectedLabel: string | null
  metric: WorkbenchMindMetric
  loading: boolean
  error: string | null
  dateFrom: string
  dateTo: string
  brandLabel: string
}>()

const emit = defineEmits<{
  select: [primaryLabel: string]
  metric: [value: WorkbenchMindMetric]
  retry: []
  openVoice: [primaryLabel: string]
}>()

const dimensions = computed(() => props.mind?.dimensions ?? [])
const preparing = computed(() => props.mind?.snapshot_status === 'preparing')
const selected = computed(() =>
  dimensions.value.find((item) => item.primary_label === props.selectedLabel)
    ?? dimensions.value[0]
    ?? null,
)
const chartElement = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null
const centerSize = ref(40)

/** 根据当前切换维度返回条形图值；占比与正向率都以 0..1 Contract 展示。 */
function metricValue(item: WorkbenchMindDimensionResponse): number {
  return props.metric === 'share' ? item.content_share : item.positive_rate ?? 0
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

/** 切换帖子占比/正向率只改变当前卡片表现层，不改变查询口径。 */
function setMetric(value: WorkbenchMindMetric): void {
  emit('metric', value)
}

/** active Taxonomy 的每个业务一级标签对应一条雷达轴，数量变化时自然形成 N 边图。 */
function renderChart(): void {
  if (!chartElement.value || dimensions.value.length === 0) return
  if (!chart) {
    chart = echarts.init(chartElement.value, undefined, { renderer: 'svg' })
    chart.on('click', (event) => {
      if (event.componentType !== 'radar') return
      const label = String(event.name ?? '')
      if (dimensions.value.some((item) => item.primary_label === label)) emit('select', label)
    })
  }
  const values = dimensions.value.map(metricValue)
  const context = document.createElement('canvas').getContext('2d')
  const fontFamily = getComputedStyle(chartElement.value).fontFamily
  const labels = dimensions.value.map((item) => `${item.primary_label} ${percent(metricValue(item))}`)
  const geometry = radarGeometry(chartElement.value.clientWidth, chartElement.value.clientHeight, labels, (text, size) => {
    if (!context) return text.length * size
    context.font = `600 ${size}px ${fontFamily}`
    return context.measureText(text).width
  })
  centerSize.value = Math.max(28, Math.min(58, geometry.radius * 0.64))
  const displayLabels = new Map(dimensions.value.map((item, index) => [item.primary_label, geometry.labels[index]?.label]))
  chartElement.value.dataset.labelGeometry = JSON.stringify(geometry.labels)
  chartElement.value.dataset.labelFontSize = String(geometry.fontSize)
  chart.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#fff',
      borderColor: '#ed0b68',
      borderWidth: 1,
      textStyle: { color: '#17233d', fontSize: 11 },
      formatter: () => dimensions.value
        .map((item) => `${echarts.format.encodeHTML(item.primary_label)}　<b>${percent(metricValue(item))}</b>`)
        .join('<br/>'),
    },
    radar: {
      center: ['50%', '50%'],
      radius: geometry.radius,
      shape: 'polygon',
      splitNumber: 4,
      startAngle: 90,
      indicator: dimensions.value.map((item) => ({ name: item.primary_label, max: 1 })),
      axisNameGap: geometry.gap,
      axisName: {
        color: '#17233d',
        fontSize: geometry.fontSize,
        fontWeight: 600,
        lineHeight: geometry.fontSize + 3,
        formatter: (name: string) => displayLabels.get(name) ?? name,
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
      symbolSize: Math.max(3, Math.min(7, geometry.radius / 14)),
      lineStyle: { color: '#ed0b68', width: 2.5 },
      itemStyle: { color: '#fff', borderColor: '#ed0b68', borderWidth: 2 },
      areaStyle: { color: 'rgba(237, 11, 104, .34)' },
      data: [{ value: values }],
    }],
  }, true)
}

watch(chartElement, async (element) => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
  if (!element) return
  await nextTick()
  if (chartElement.value !== element) return
  renderChart()
  observer = new ResizeObserver(() => { chart?.resize(); renderChart() })
  observer.observe(element)
}, { flush: 'post' })

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
    <header class="card-header">
      <div class="title">
        <span>◎</span>
        <div>
          <h2>品牌用户心智</h2>
          <p>基于当前 active Taxonomy，动态查看一级用户心智</p>
        </div>
      </div>
      <div class="header-actions">
        <WorkbenchDateLabel
          :from="dateFrom"
          :to="dateTo"
        />
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
      <div
        class="card-refresh-state"
        role="status"
      >
        <template v-if="(error && mind) || mind?.snapshot_status === 'failed'">
          <span>{{ mind?.computed_at ? '更新失败，保留上次结果' : '聚合失败' }}</span><button
            type="button"
            @click="emit('retry')"
          >
            重试
          </button>
        </template>
        <span v-else-if="loading || mind?.snapshot_status === 'refreshing'">更新中…</span>
      </div>
    </header>

    <div
      v-if="error && !mind"
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
      v-else-if="preparing"
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
            :style="{ width: `${centerSize}px`, height: `${centerSize}px` }"
            aria-hidden="true"
          >
            <strong :title="brandLabel">{{ brandLabel }}</strong><span>心智图</span>
          </div>
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
        class="mind-detail aima-scroll-card"
      >
        <small>当前查看 · 一级心智 · {{ metric === 'share' ? '帖子占比' : '正向率' }}</small>
        <div class="detail-title">
          <h3 :title="selected.primary_label">
            {{ selected.primary_label }}
          </h3>
          <span>{{ changeText(selected.content_share_change_pp) }}</span>
        </div>
        <div class="metric-cards">
          <div>
            <span>心智占比</span>
            <strong>{{ percent(selected.content_share) }}</strong>
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
            {{ item.secondary_label }} · {{ item.content_count }} 条
          </span>
          <span v-if="selected.secondary_labels.length === 0">暂无二级标签内容</span>
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
      <span>相关内容 {{ mind.relevant_content_count.toLocaleString('zh-CN') }} 条</span>
      <span>当前规则覆盖 {{ (mind.analysis_coverage_rate * 100).toFixed(1) }}%</span>
    </footer>
  </section>
</template>

<style scoped>
.card-header { position: relative; flex: none; }
.card-refresh-state { position: absolute; bottom: 1px; right: 12px; display: flex; gap: 5px; color: var(--aima-text-muted); font-size: 9px; line-height: 11px; }
.card-refresh-state button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font: inherit; }
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
.mind-body { display: grid; min-height: 0; flex: 1; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
.mind-radar { display: flex; min-width: 0; min-height: 0; flex-direction: column; padding: clamp(6px, 1.1cqw, 12px); border-right: 1px solid var(--aima-border); }
.radar-title { display: flex; min-height: 18px; flex: none; align-items: center; justify-content: space-between; gap: 5px; }
.radar-title strong { color: var(--aima-text); font-size: 12px; }
.radar-title span { color: var(--aima-text-disabled); font-size: 10px; white-space: nowrap; }
.radar-stage { position: relative; min-height: 0; flex: 1; }
.radar-chart { width: 100%; height: 100%; min-height: 0; }
.radar-center { position: absolute; top: 50%; left: 50%; display: grid; place-content: center; transform: translate(-50%, -50%); border-radius: 50%; color: #fff; background: var(--aima-primary); text-align: center; pointer-events: none; }
.radar-center strong { max-width: 54px; overflow: hidden; font-size: clamp(10px, 1.7cqw, 14px); text-overflow: ellipsis; white-space: nowrap; }
.radar-center span { font-size: 9px; }
.radar-accessible-list { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.mind-detail { display: flex; min-width: 0; min-height: 0; flex-direction: column; gap: clamp(5px, .9cqw, 10px); padding: clamp(7px, 1.2cqw, 14px); overflow: auto; }
.mind-detail > small { color: var(--aima-text-disabled); font-size: 11px; }
.detail-title { display: grid; gap: 2px; }
.detail-title h3 { min-width: 0; margin: 0; color: var(--aima-text); font-size: clamp(14px, 2cqw, 18px); line-height: 1.35; overflow-wrap: anywhere; }
.detail-title span { color: var(--aima-primary); font-size: 11px; }
.metric-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.metric-cards div { display: grid; min-height: 44px; align-content: center; gap: 2px; padding: 5px 7px; border-radius: 7px; background: var(--aima-surface-disabled); }
.metric-cards span { color: var(--aima-text-muted); font-size: 11px; }
.metric-cards strong { color: var(--aima-text); font-size: clamp(16px, 2.3cqw, 22px); }
.secondary { display: grid; gap: 2px; }
.secondary strong { color: var(--aima-text); font-size: 11px; }
.secondary span { color: var(--aima-text-secondary); font-size: 11px; line-height: 1.3; }
.change-card { padding: 5px 7px; border-left: 2px solid var(--aima-primary); border-radius: 6px; background: var(--aima-primary-soft); }
.change-card strong { color: var(--aima-text); font-size: 11px; }
.change-card p { margin: 2px 0 0; color: var(--aima-text-secondary); font-size: 11px; line-height: 1.3; }
.voice-link, .module-state button { align-self: flex-start; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; font-weight: 600; }
.module-state { display: grid; min-height: 220px; place-content: center; gap: 5px; color: var(--aima-text-disabled); text-align: center; font-size: 12px; }
.module-state--error { color: var(--aima-danger); }
.module-state--error span { color: var(--aima-text-secondary); }
.module-state--inline { min-height: 0; grid-template-columns: auto auto auto; align-items: center; justify-content: start; margin: 5px 12px 0; padding: 5px 8px; border-radius: 5px; background: var(--aima-primary-soft); text-align: left; font-size: 10px; }
@container (max-height: 400px) {
  .mind-detail { gap: 3px; padding: 6px 9px; }
  .detail-title h3 { font-size: 15px; }
  .metric-cards div { min-height: 36px; padding: 4px 6px; }
  .metric-cards strong { font-size: 18px; }
  .change-card { padding: 4px 6px; }
}
footer { display: flex; min-height: 26px; align-items: center; justify-content: space-between; padding: 5px 12px; border-top: 1px solid var(--aima-border); color: var(--aima-text-disabled); font-size: 9px; }
</style>
