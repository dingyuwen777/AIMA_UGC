<script setup lang="ts">
import type { CollectionRuntimeSummaryResponse } from '../../../../../generated/api/client'

const props = defineProps<{
  summary: CollectionRuntimeSummaryResponse | null
  loading: boolean
}>()

/** KPI 在首次加载时保持占位符，已有摘要刷新期间继续保留上一帧业务值。 */
function value(value: number | undefined): string {
  if (props.loading && !props.summary) return '—'
  return (value ?? 0).toLocaleString('zh-CN')
}
</script>

<template>
  <section
    class="kpi-grid"
    aria-label="采集运行概览"
  >
    <article class="kpi-card kpi-card--blue">
      <span>处理中</span>
      <strong>{{ value(summary?.processing_count) }}</strong>
    </article>
    <article class="kpi-card kpi-card--green">
      <span>今日完成</span>
      <strong>{{ value(summary?.completed_today_count) }}</strong>
    </article>
    <article class="kpi-card kpi-card--primary">
      <span>今日任务入库量</span>
      <strong>{{ value(summary?.contents_ingested_today) }}</strong>
      <small>各任务累计，可能包含重复内容</small>
    </article>
  </section>
</template>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
.kpi-card { display: flex; min-height: 108px; flex-direction: column; align-items: flex-start; gap: 4px; padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); background: var(--aima-surface); overflow: hidden; }
.kpi-card span { color: var(--aima-text-muted); font-size: 13px; font-weight: 500; line-height: 20px; }
.kpi-card strong { font-size: 28px; line-height: 36px; }
.kpi-card small { color: var(--aima-text-muted); font-size: 11px; line-height: 15px; }
.kpi-card--blue strong { color: var(--aima-color-info); }
.kpi-card--green strong { color: var(--aima-color-success); }
.kpi-card--primary strong { color: var(--aima-primary); }
@media (max-width: 920px) { .kpi-grid { grid-template-columns: 1fr; } .kpi-card { height: auto; } }
</style>
