<script setup lang="ts">
import AimaDateRange from '../../../shared/ui/AimaDateRange.vue'
import type { WorkbenchMindMetric } from '../store'

defineProps<{
  from: string
  to: string
  label?: string
  metric: WorkbenchMindMetric
}>()

const emit = defineEmits<{
  'update:range': [value: { from: string; to: string }]
  metric: [value: WorkbenchMindMetric]
}>()
</script>

<template>
  <div
    class="workbench-filter-slot aima-scroll-x"
    aria-label="品牌用户心智筛选器"
  >
    <AimaDateRange
      class="workbench-date"
      :label="label ?? '时间范围'"
      :from="from"
      :to="to"
      @update:range="emit('update:range', $event)"
    />
    <div class="metric-toggle">
      <button
        type="button"
        :class="{ active: metric === 'share' }"
        @click="emit('metric', 'share')"
      >
        心智占比
      </button>
      <button
        type="button"
        :class="{ active: metric === 'positive' }"
        @click="emit('metric', 'positive')"
      >
        正向率
      </button>
    </div>
  </div>
</template>

<style scoped>
.workbench-filter-slot {
  display: flex;
  min-width: 0;
  min-height: 42px;
  margin: 8px 12px 0;
  flex: none;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border: 1px solid var(--aima-border);
  border-radius: 7px;
  background: #fef7ff;
  overscroll-behavior-inline: contain;
}
.workbench-date { width: 205px; }
.workbench-date :deep(.date-trigger) { height: 30px; border-radius: 6px; font-size: 11px; }
.metric-toggle { display: flex; flex: none; padding: 2px; border-radius: 6px; background: var(--aima-surface-disabled); }
.metric-toggle button { padding: 4px 7px; border: 0; border-radius: 4px; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 10px; }
.metric-toggle .active { color: var(--aima-primary); background: var(--aima-primary-soft); font-weight: 700; }
</style>
