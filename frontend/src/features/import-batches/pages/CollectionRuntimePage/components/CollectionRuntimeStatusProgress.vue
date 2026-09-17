<script setup lang="ts">
import type { CollectionRuntimeStatus } from '../../../../../generated/api/client'
import { runtimeStatusLabels } from '../../../format'

const props = defineProps<{
  status: CollectionRuntimeStatus
  progress: number
}>()

/** 进度宽度限制在可显示范围内，异常服务端值不能撑破状态单元格。 */
function progressWidth(): string {
  return `${Math.max(0, Math.min(100, props.progress))}%`
}
</script>

<template>
  <div :class="['status-progress', `status-progress--${status}`]">
    <div class="status-row">
      <span class="status-pill">{{ runtimeStatusLabels[status] }}</span>
      <strong>{{ progress }}%</strong>
    </div>
    <div class="progress-track">
      <span :style="{ width: progressWidth() }" />
    </div>
  </div>
</template>

<style scoped>
.status-progress { width: 100%; }
.status-row { display: flex; align-items: center; justify-content: center; gap: 8px; color: var(--aima-color-info); font-size: 12px; font-weight: 700; line-height: 18px; }
.status-pill { padding: 2px 8px; border-radius: var(--aima-radius-full); background: var(--aima-color-info-bg); white-space: nowrap; }
.status-row strong { font: inherit; white-space: nowrap; }
.progress-track { width: 100%; height: 4px; margin-top: 6px; overflow: hidden; border-radius: 2px; background: var(--aima-color-info-bg); }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: var(--aima-color-info); }
.status-progress--succeeded .status-row { color: var(--aima-color-success); }
.status-progress--succeeded .status-pill,
.status-progress--succeeded .progress-track { background: var(--aima-color-success-bg); }
.status-progress--succeeded .progress-track span { background: var(--aima-color-success); }
.status-progress--partial_success .status-row { color: var(--aima-color-warning); }
.status-progress--partial_success .status-pill,
.status-progress--partial_success .progress-track { background: var(--aima-color-warning-bg); }
.status-progress--partial_success .progress-track span { background: var(--aima-color-warning); }
.status-progress--failed .status-row,
.status-progress--cancelled .status-row { color: var(--aima-color-error); }
.status-progress--failed .status-pill,
.status-progress--failed .progress-track,
.status-progress--cancelled .status-pill,
.status-progress--cancelled .progress-track { background: var(--aima-color-error-bg); }
.status-progress--failed .progress-track span,
.status-progress--cancelled .progress-track span { background: var(--aima-color-error); }
</style>
