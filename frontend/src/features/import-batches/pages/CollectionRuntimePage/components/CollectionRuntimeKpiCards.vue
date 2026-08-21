<script setup lang="ts">
import type { CollectionRuntimeSummaryResponse } from '../../../../../generated/api/client'
import { formatNumber } from '../../../format'

defineProps<{ summary: CollectionRuntimeSummaryResponse | null; loading: boolean }>()
</script>

<template>
  <section
    class="kpi-grid"
    aria-label="采集运行概览"
  >
    <article class="kpi-card kpi-card--blue">
      <span class="kpi-icon">▶</span>
      <div><span>处理中</span><strong>{{ loading && !summary ? '—' : formatNumber(summary?.processing_count) }}</strong></div>
    </article>
    <article class="kpi-card kpi-card--green">
      <span class="kpi-icon">✓</span>
      <div><span>今日完成</span><strong>{{ loading && !summary ? '—' : formatNumber(summary?.completed_today_count) }}</strong></div>
    </article>
    <article class="kpi-card kpi-card--purple">
      <span class="kpi-icon">▤</span>
      <div><span>今日入库内容</span><strong>{{ loading && !summary ? '—' : formatNumber(summary?.contents_ingested_today) }}</strong></div>
    </article>
  </section>
</template>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 22px 0; }
.kpi-card { display: flex; min-height: 110px; align-items: center; gap: 17px; padding: 22px 26px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; box-shadow: 0 2px 8px rgb(23 32 51 / 3%); }
.kpi-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: 50%; color: #fff; font-size: 20px; }
.kpi-card--blue .kpi-icon { background: #2563eb; }
.kpi-card--green .kpi-icon { background: #16a05d; }
.kpi-card--purple .kpi-icon { background: #9454db; }
.kpi-card div span, .kpi-card div strong { display: block; }
.kpi-card div span { color: #596275; font-size: 14px; }
.kpi-card div strong { margin-top: 5px; color: #182033; font-size: 27px; line-height: 1; }
</style>
