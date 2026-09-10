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
      <span class="summary-icon is-green"><AimaIcon name="strategy" /></span><div><p>启用品牌</p><strong>{{ loading ? '—' : brandCount }}</strong></div>
    </article>
    <article class="summary-item">
      <span class="summary-icon is-purple"><AimaIcon name="runtime" /></span><div><p>启用计划</p><strong>{{ loading ? '—' : enabledPlanCount }}</strong></div>
    </article>
  </section>
</template>

<style scoped>
.strategy-summary { display: grid; min-height: 88px; grid-template-columns: repeat(3, 1fr); margin: 20px 0; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }
.summary-item { display: flex; min-width: 0; align-items: center; gap: 14px; padding: 17px 24px; }
.summary-item + .summary-item { border-left: 1px solid var(--aima-border); }
.summary-icon { display: grid; width: 38px; height: 38px; flex: none; place-items: center; border-radius: 50%; color: #fff; }
.is-blue { background: #1677ff; }.is-green { background: #16b364; }.is-purple { background: #7c3aed; }
p { margin: 0 0 3px; color: var(--aima-text-muted); font-size: 12px; line-height: 17px; }
strong { display: block; max-width: 250px; overflow: hidden; color: var(--aima-text); font-size: 22px; font-weight: 650; line-height: 26px; text-overflow: ellipsis; white-space: nowrap; }
</style>
