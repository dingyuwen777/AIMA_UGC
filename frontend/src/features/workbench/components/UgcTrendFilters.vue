<script setup lang="ts">
import { computed } from 'vue'

import type { ContentAnalysisTaxonomyResponse } from '../../../generated/api/client'
import AimaDateRange from '../../../shared/ui/AimaDateRange.vue'
import AimaMultiSelect, { type AimaSelectOption } from '../../../shared/ui/AimaMultiSelect.vue'

const props = defineProps<{
  from: string
  to: string
  voiceTypes: string[]
  taxonomy: ContentAnalysisTaxonomyResponse | null
}>()

const emit = defineEmits<{
  'update:range': [value: { from: string; to: string }]
  'update:voice-types': [value: string[]]
}>()

const voiceTypeOptions = computed<AimaSelectOption[]>(() =>
  (props.taxonomy?.voice_types ?? []).map((value) => ({ value, label: value })),
)
</script>

<template>
  <div
    class="ugc-trend-filters aima-scroll-x"
    aria-label="UGC 趋势筛选器"
  >
    <AimaDateRange
      class="workbench-date"
      label="UGC 声量与情感趋势时间范围"
      :from="from"
      :to="to"
      @update:range="emit('update:range', $event)"
    />
    <AimaMultiSelect
      label="发声类型"
      :model-value="voiceTypes"
      :options="voiceTypeOptions"
      @update:model-value="emit('update:voice-types', $event)"
    />
  </div>
</template>

<style scoped>
.ugc-trend-filters {
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
</style>
