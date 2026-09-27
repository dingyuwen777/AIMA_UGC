<script setup lang="ts">
import { computed } from 'vue'

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
const selected = computed(() =>
  dimensions.value.find((item) => item.primary_label === props.selectedLabel)
    ?? dimensions.value[0]
    ?? null,
)

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
</script>

<template>
  <section class="mind-card">
    <header>
      <div class="title">
        <span>◎</span>
        <div>
          <h2>品牌用户心智</h2>
          <p>基于当前 active Taxonomy，动态查看一级用户心智</p>
        </div>
      </div>
      <div class="header-actions">
        <small>全网 · {{ mind ? `${mind.date_from} — ${mind.date_to}` : '近30天' }}</small>
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

    <div
      v-if="error"
      class="module-state module-state--error"
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
      v-if="loading && dimensions.length === 0"
      class="module-state"
    >
      正在聚合当前 active Taxonomy…
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
      <div class="ranking">
        <div class="ranking-title">
          <strong>{{ metric === 'share' ? '一级心智用户占比' : '一级心智正向率' }}</strong>
          <span v-if="metric === 'share'">多标签独立统计 · 可合计&gt;100%</span>
          <span v-else>仅 relevant · 正面 / relevant</span>
        </div>
        <button
          v-for="item in dimensions"
          :key="item.primary_label"
          type="button"
          :class="{ selected: selected?.primary_label === item.primary_label }"
          @click="emit('select', item.primary_label)"
        >
          <span class="label">{{ item.primary_label }}</span>
          <span class="track"><i :style="{ width: `${Math.max(2, metricValue(item) * 100)}%` }" /></span>
          <strong>{{ percent(metricValue(item)) }}</strong>
        </button>
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
.ranking { min-width: 0; overflow: auto; padding: 12px; border-right: 1px solid var(--aima-border); }
.ranking-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.ranking-title strong { color: var(--aima-text); font-size: 12px; }
.ranking-title span { color: var(--aima-text-disabled); font-size: 9px; white-space: nowrap; }
.ranking > button { display: grid; width: 100%; min-height: 28px; grid-template-columns: minmax(88px, .8fr) minmax(80px, 1.4fr) 48px; align-items: center; gap: 7px; padding: 3px 6px; border: 0; border-radius: 5px; color: var(--aima-text); background: transparent; cursor: pointer; text-align: left; }
.ranking > button:hover, .ranking > button.selected { background: var(--aima-color-bg-hover); }
.ranking .label { overflow: hidden; font-size: 10px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.track { height: 7px; overflow: hidden; border-radius: 4px; background: var(--aima-surface-disabled); }
.track i { display: block; height: 100%; max-width: 100%; border-radius: inherit; background: var(--aima-primary); }
.ranking > button > strong { color: var(--aima-primary); font-size: 10px; text-align: right; }
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
footer { display: flex; min-height: 26px; align-items: center; justify-content: space-between; padding: 5px 12px; border-top: 1px solid var(--aima-border); color: var(--aima-text-disabled); font-size: 9px; }
@media (max-width: 1180px) {
  .mind-body { grid-template-columns: minmax(0, 1fr); overflow: auto; }
  .ranking { border-right: 0; border-bottom: 1px solid var(--aima-border); }
}
</style>
