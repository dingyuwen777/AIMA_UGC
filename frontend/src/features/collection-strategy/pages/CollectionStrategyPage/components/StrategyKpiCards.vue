<script setup lang="ts">
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

defineProps<{
  packCount: number
  brandCount: number
  enabledPlanCount: number
  loading: boolean
}>()
</script>

<template>
  <section
    class="strategy-summary"
    aria-label="采集策略摘要"
  >
    <article class="summary-item">
      <span class="summary-icon is-blue"><AimaIcon name="search" /></span><div><p>关键词包</p><strong>{{ loading ? '—' : packCount }}</strong></div>
    </article>
    <article class="summary-item">
      <span class="summary-icon is-green"><AimaIcon name="strategy" /></span><div><p>启用品牌</p><strong class="brand-value">{{ loading ? '—' : `${brandCount} 个品牌` }}</strong></div>
    </article>
    <article class="summary-item">
      <span class="summary-icon is-purple"><AimaIcon name="runtime" /></span><div><p>启用计划</p><strong>{{ loading ? '—' : enabledPlanCount }}</strong></div>
    </article>
  </section>
</template>

<style scoped>
.strategy-summary {
  display: grid;
  height: 88px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 20px 0;
}
.summary-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
  padding: 17px 24px;
  overflow: hidden;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: #fff;
}
.summary-icon { display: grid; width: 36px; height: 36px; flex: none; place-items: center; border-radius: 50%; color: #fff; }
.is-blue { background: #1677ff; }.is-green { background: #12b76a; }.is-purple { background: #7c3aed; }
p { margin: 0 0 2px; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
strong { display: block; max-width: 250px; overflow: hidden; color: var(--aima-text); font-size: 26px; font-weight: 700; line-height: 32px; text-overflow: ellipsis; white-space: nowrap; }
.brand-value { font-size: 22px; font-weight: 500; line-height: 30px; }
</style>
