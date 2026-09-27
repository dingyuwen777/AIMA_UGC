<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { WorkbenchTrendResponse } from '../../../generated/api/client'

const props = defineProps<{
  trend: WorkbenchTrendResponse | null
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  retry: []
  openDay: [day: string]
}>()

const chartElement = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

const positivePercent = computed(() => Math.round((props.trend?.positive_rate ?? 0) * 100))
const donutStyle = computed(() => ({
  background: `conic-gradient(var(--aima-success) ${positivePercent.value}%, var(--aima-surface-disabled) 0)`,
}))
const palette = ['#22c55e', '#7f8a9c', '#ef4444', '#8b5cf6', '#a8b0bf', '#1677ff', '#d97706']

/** 百分率支持空值；比例类字段按产品界面统一显示一位小数。 */
function percent(value: number | null | undefined): string {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

/** 周期变化按百分比显示，前一期为 0 时 Contract 返回空值。 */
function changeRate(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(1)}%`
}

/** pp 变化使用显式符号，避免把百分点与百分比混淆。 */
function changePp(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}pp`
}

/** 情感颜色按 active Taxonomy 当前顺序循环，不维护另一套业务枚举。 */
function sentimentColor(index: number): string {
  return palette[index % palette.length] ?? '#7f8a9c'
}

/** 把后端 daily 序列绘成 Figma 对应的平滑面积折线，数据本身不在前端重算。 */
function renderChart(): void {
  if (!chartElement.value) return
  if (!chart) chart = echarts.init(chartElement.value)
  const daily = props.trend?.daily ?? []
  chart.setOption({
    animationDuration: 280,
    grid: { left: 42, right: 10, top: 18, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : []
        const first = list[0] as { axisValue?: string; data?: number } | undefined
        return first ? `${first.axisValue}<br/><b>当天声量 ${Number(first.data ?? 0).toLocaleString('zh-CN')} 条</b>` : ''
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: daily.map((item) => item.day.slice(5).replace('-', '/')),
      axisLine: { lineStyle: { color: '#e6eaf0' } },
      axisTick: { show: false },
      axisLabel: { color: '#8e9aa8', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#eef1f5' } },
      axisLabel: { color: '#8e9aa8', fontSize: 10 },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: daily.map((item) => item.count),
      lineStyle: { width: 2, color: '#e6005c' },
      itemStyle: { color: '#e6005c' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230,0,92,.22)' },
          { offset: 1, color: 'rgba(230,0,92,.01)' },
        ]),
      },
    }],
  }, true)
}

/** 图表容器 resize 后让 ECharts 重新读取真实卡片尺寸。 */
function resizeChart(): void {
  chart?.resize()
}

onMounted(async () => {
  await nextTick()
  renderChart()
  if (chartElement.value) {
    observer = new ResizeObserver(resizeChart)
    observer.observe(chartElement.value)
  }
})

watch(() => props.trend?.daily, async () => {
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
  <section class="trend-card">
    <header>
      <div class="title">
        <span>↗</span>
        <div>
          <h2>UGC 声量与情感趋势</h2>
          <p>关注每日声量起伏与当前生效分析规则下的情感变化</p>
        </div>
      </div>
      <small>{{ trend ? `${trend.date_from} — ${trend.date_to}` : '近30天' }}</small>
    </header>

    <div
      v-if="error"
      class="module-state module-state--error"
      role="alert"
    >
      <strong>趋势数据暂时无法更新</strong>
      <span>继续保留上次成功结果。</span>
      <button
        type="button"
        @click="emit('retry')"
      >
        重试
      </button>
    </div>
    <div
      v-if="loading && !trend"
      class="module-state"
    >
      正在计算声量与情感趋势…
    </div>
    <div
      v-else-if="!trend && !error"
      class="module-state"
    >
      当前筛选范围暂无趋势数据
    </div>

    <div
      v-else-if="trend"
      class="trend-body"
    >
      <div class="trend-main">
        <div class="kpis">
          <div><span>总声量</span><strong>{{ trend.total_count.toLocaleString('zh-CN') }}</strong></div>
          <div><span>日均声量</span><strong>{{ trend.daily_average.toLocaleString('zh-CN') }}</strong></div>
          <div><span>单日峰值</span><strong>{{ trend.peak_count.toLocaleString('zh-CN') }}</strong></div>
          <div class="emphasis"><span>较上期</span><strong>{{ changeRate(trend.period_change_rate) }}</strong></div>
        </div>
        <div
          ref="chartElement"
          class="trend-chart"
          aria-label="UGC 每日声量趋势图"
        />
        <div class="insight-card">
          <span>统计</span>
          <div>
            <strong>趋势摘要</strong>
            <p>{{ trend.summary }}</p>
          </div>
          <button
            type="button"
            :disabled="!trend.peak_day"
            @click="trend.peak_day && emit('openDay', trend.peak_day)"
          >
            查看当天内容 →
          </button>
        </div>
      </div>

      <aside>
        <div class="sentiment-title">
          <strong>UGC 情感结构</strong>
          <span>情感维度来自当前 active Taxonomy</span>
        </div>
        <div
          class="positive-ring"
          :style="donutStyle"
        >
          <div>
            <span>正向率</span>
            <strong>{{ percent(trend.positive_rate) }}</strong>
            <small>仅统计 relevant</small>
          </div>
        </div>
        <div class="sentiment-list">
          <div
            v-for="(item, index) in trend.sentiments"
            :key="item.sentiment"
          >
            <i :style="{ background: sentimentColor(index) }" />
            <span>{{ item.sentiment }}</span>
            <strong>{{ percent(item.share) }}</strong>
          </div>
        </div>
        <div class="rate-change">
          <span>正向率较上期</span>
          <strong>{{ changePp(trend.positive_rate_change_pp) }}</strong>
        </div>
        <small class="coverage">当前规则覆盖 {{ (trend.analysis_coverage_rate * 100).toFixed(1) }}%</small>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.trend-card { display: flex; height: 100%; min-width: 0; flex-direction: column; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); box-shadow: 0 4px 12px -2px rgb(23 35 61 / 4%), 0 1px 6px rgb(23 35 61 / 8%); }
header { display: flex; min-height: 56px; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--aima-border); }
.title { display: flex; min-width: 0; align-items: center; gap: 8px; }
.title > span { display: grid; width: 28px; height: 28px; flex: none; place-items: center; border-radius: 50%; color: var(--aima-primary); background: var(--aima-primary-soft); }
.title h2, .title p { margin: 0; }
.title h2 { color: var(--aima-text); font-size: 16px; }
.title p { margin-top: 2px; color: var(--aima-text-secondary); font-size: 11px; }
header > small { color: var(--aima-text-disabled); font-size: 10px; }
.trend-body { display: grid; min-height: 0; flex: 1; grid-template-columns: minmax(0, 1fr) 190px; gap: 10px; padding: 10px; }
.trend-main { display: grid; min-width: 0; grid-template-rows: auto minmax(150px, 1fr) auto; gap: 8px; }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 5px; }
.kpis > div { display: grid; gap: 3px; padding: 7px 8px; border: 1px solid var(--aima-border); border-radius: 5px; }
.kpis span { color: var(--aima-text-disabled); font-size: 9px; }
.kpis strong { color: var(--aima-text); font-size: 15px; }
.kpis .emphasis { background: var(--aima-color-error-bg); }
.kpis .emphasis strong { color: var(--aima-primary); }
.trend-chart { min-height: 160px; }
.insight-card { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 5px; background: #f6f5fe; }
.insight-card > span { padding: 2px 5px; border-radius: 3px; color: #fff; background: #8b5cf6; font-size: 9px; font-weight: 700; }
.insight-card strong { color: var(--aima-text); font-size: 10px; }
.insight-card p { margin: 2px 0 0; color: var(--aima-text-secondary); font-size: 9px; line-height: 14px; }
.insight-card button, .module-state button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 9px; font-weight: 700; white-space: nowrap; }
.insight-card button:disabled { color: var(--aima-text-disabled); cursor: default; }
aside { display: flex; min-width: 0; flex-direction: column; gap: 8px; padding: 8px; border: 1px solid var(--aima-border); border-radius: 6px; }
.sentiment-title { display: grid; gap: 2px; }
.sentiment-title strong { color: var(--aima-text); font-size: 11px; }
.sentiment-title span { color: var(--aima-text-disabled); font-size: 8px; line-height: 12px; }
.positive-ring { display: grid; width: 104px; height: 104px; flex: none; place-self: center; place-items: center; border-radius: 50%; }
.positive-ring > div { display: grid; width: 74px; height: 74px; place-content: center; border-radius: 50%; background: #fff; text-align: center; }
.positive-ring span, .positive-ring small { color: var(--aima-text-disabled); font-size: 8px; }
.positive-ring strong { color: var(--aima-success); font-size: 20px; }
.sentiment-list { display: grid; min-height: 0; gap: 3px; overflow: auto; }
.sentiment-list > div { display: grid; grid-template-columns: 7px minmax(0, 1fr) auto; align-items: center; gap: 5px; color: var(--aima-text); font-size: 9px; }
.sentiment-list i { width: 5px; height: 5px; border-radius: 50%; }
.sentiment-list strong { font-size: 9px; }
.rate-change { display: flex; justify-content: space-between; padding-top: 6px; border-top: 1px solid var(--aima-border); color: var(--aima-text-secondary); font-size: 9px; }
.rate-change strong { color: var(--aima-primary); }
.coverage { margin-top: auto; color: var(--aima-text-disabled); font-size: 8px; }
.module-state { display: grid; min-height: 220px; place-content: center; gap: 5px; color: var(--aima-text-disabled); text-align: center; font-size: 12px; }
.module-state--error { color: var(--aima-danger); }
.module-state--error span { color: var(--aima-text-secondary); }
@media (max-width: 1050px) {
  .trend-body { grid-template-columns: minmax(0, 1fr); overflow: auto; }
  aside { display: grid; grid-template-columns: minmax(130px, .8fr) 110px minmax(150px, 1fr); align-items: center; }
  .sentiment-title, .rate-change, .coverage { grid-column: 1; }
  .positive-ring { grid-column: 2; grid-row: 1 / span 3; }
  .sentiment-list { grid-column: 3; grid-row: 1 / span 3; }
}
</style>
