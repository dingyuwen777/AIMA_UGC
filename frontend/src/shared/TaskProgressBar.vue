<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  value?: number | null
  detail?: string
  compact?: boolean
  indeterminate?: boolean
  tone?: 'primary' | 'success' | 'warning' | 'danger'
}>(), {
  value: null,
  detail: '',
  compact: false,
  indeterminate: false,
  tone: 'primary',
})

/** 统一截断异常输入，避免视觉宽度或 ARIA 数值越界。 */
const normalizedValue = computed(() => {
  const value = Number.isFinite(props.value) ? Number(props.value) : 0
  return Math.max(0, Math.min(100, Math.round(value)))
})
</script>

<template>
  <section
    class="task-progress"
    :class="[`task-progress--${tone}`, { 'task-progress--compact': compact }]"
  >
    <div class="task-progress__heading">
      <strong>{{ label }}</strong>
      <span v-if="detail">{{ detail }}</span>
      <b v-if="!indeterminate">{{ normalizedValue }}%</b>
    </div>
    <div
      class="task-progress__track"
      role="progressbar"
      :aria-label="label"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="indeterminate ? undefined : normalizedValue"
      :aria-valuetext="detail || undefined"
    >
      <span
        class="task-progress__fill"
        :class="{ 'task-progress__fill--indeterminate': indeterminate }"
        :style="indeterminate ? undefined : { width: `${normalizedValue}%` }"
      />
    </div>
  </section>
</template>

<style scoped>
.task-progress { display: grid; gap: 7px; min-width: 0; }
.task-progress__heading { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: center; color: #687386; font-size: 11px; }
.task-progress__heading strong { color: #354052; font-size: 12px; }
.task-progress__heading span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-progress__heading b { color: #2563eb; font-size: 11px; }
.task-progress__track { position: relative; height: 7px; overflow: hidden; border-radius: 999px; background: #edf1f7; }
.task-progress__fill { display: block; height: 100%; border-radius: inherit; background: #2563eb; transition: width .2s ease; }
.task-progress--success .task-progress__fill { background: #16a05d; }
.task-progress--success .task-progress__heading b { color: #12804b; }
.task-progress--warning .task-progress__fill { background: #d48709; }
.task-progress--warning .task-progress__heading b { color: #a86100; }
.task-progress--danger .task-progress__fill { background: #e5484d; }
.task-progress--danger .task-progress__heading b { color: #cf3440; }
.task-progress--compact { gap: 5px; }
.task-progress--compact .task-progress__heading { font-size: 10px; }
.task-progress--compact .task-progress__heading strong { font-size: 11px; }
.task-progress--compact .task-progress__track { height: 5px; }
.task-progress__fill--indeterminate { width: 34%; animation: task-progress-slide 1.1s ease-in-out infinite; }

@keyframes task-progress-slide {
  from { transform: translateX(-110%); }
  to { transform: translateX(310%); }
}

@media (prefers-reduced-motion: reduce) {
  .task-progress__fill { transition: none; }
  .task-progress__fill--indeterminate { width: 100%; animation: none; opacity: .55; }
}
</style>
