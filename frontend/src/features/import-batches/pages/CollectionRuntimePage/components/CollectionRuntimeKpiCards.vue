<script setup lang="ts">
import type { CollectionRuntimeSummaryResponse } from '../../../../../generated/api/client'

const props = defineProps<{
  summary: CollectionRuntimeSummaryResponse | null
  loading: boolean
}>()

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
      <span>今日入库内容</span>
      <strong>{{ value(summary?.contents_ingested_today) }}</strong>
    </article>
  </section>
</template>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
.kpi-card { display: flex; height: 92px; flex-direction: column; align-items: flex-start; gap: 6px; padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: var(--aima-surface); overflow: hidden; }
.kpi-card span { color: var(--aima-text-muted); font-size: 13px; font-weight: 500; line-height: 20px; }
.kpi-card strong { font-size: 28px; line-height: 36px; }
.kpi-card--blue strong { color: #1677ff; }
.kpi-card--green strong { color: #12b76a; }
.kpi-card--primary strong { color: var(--aima-primary); }
@media (max-width: 920px) { .kpi-grid { grid-template-columns: 1fr; } .kpi-card { height: auto; } }
</style>
