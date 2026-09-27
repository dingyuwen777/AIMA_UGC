<script setup lang="ts">
import { computed } from 'vue'

import {
  PlatformName,
  type BrandResponse,
  type ContentAnalysisTaxonomyResponse,
  type VehicleModelResponse,
} from '../../../generated/api/client'
import { platformLabel } from '../../../shared/domain/platform'
import AimaDateRange from '../../../shared/ui/AimaDateRange.vue'
import type { WorkbenchFilters } from '../store'
import WorkbenchMultiSelect, { type WorkbenchSelectOption } from './WorkbenchMultiSelect.vue'

const props = defineProps<{
  modelValue: WorkbenchFilters
  taxonomy: ContentAnalysisTaxonomyResponse | null
  brands: BrandResponse[]
  vehicleModels: VehicleModelResponse[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WorkbenchFilters]
  reset: []
}>()

const platformOptions = computed<WorkbenchSelectOption[]>(() =>
  Object.values(PlatformName).map((value) => ({ value, label: platformLabel(value) })),
)
const sentimentOptions = computed<WorkbenchSelectOption[]>(() =>
  (props.taxonomy?.sentiments ?? []).map((value) => ({ value, label: value })),
)
const voiceTypeOptions = computed<WorkbenchSelectOption[]>(() =>
  (props.taxonomy?.voice_types ?? []).map((value) => ({ value, label: value })),
)
const primaryLabelOptions = computed<WorkbenchSelectOption[]>(() =>
  (props.taxonomy?.labels ?? []).map((item) => ({
    value: item.primary_label,
    label: item.primary_label,
  })),
)
const secondaryLabelOptions = computed<WorkbenchSelectOption[]>(() =>
  (props.taxonomy?.labels ?? []).flatMap((item) =>
    item.secondary_labels.map((value) => ({
      value,
      label: `${item.primary_label} / ${value}`,
    })),
  ),
)
const brandOptions = computed<WorkbenchSelectOption[]>(() =>
  props.brands.map((item) => ({ value: item.id, label: item.display_name })),
)
const vehicleOptions = computed<WorkbenchSelectOption[]>(() => {
  const selectedBrands = new Set(props.modelValue.brandIds)
  return props.vehicleModels
    .filter((item) => selectedBrands.size === 0 || (item.brand_id && selectedBrands.has(item.brand_id)))
    .map((item) => ({ value: item.id, label: item.display_name }))
})

/** 替换一个数组筛选维度，避免子组件直接修改父级对象。 */
function updateArray(
  key: Exclude<keyof WorkbenchFilters, 'dateFrom' | 'dateTo'>,
  value: string[],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

/** 日期范围始终成对写回同一筛选快照。 */
function updateDate(key: 'dateFrom' | 'dateTo', value: string): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<template>
  <div class="workbench-filters">
    <WorkbenchMultiSelect
      label="情感"
      :model-value="modelValue.sentiments"
      :options="sentimentOptions"
      :disabled="loading"
      @update:model-value="updateArray('sentiments', $event)"
    />
    <WorkbenchMultiSelect
      label="平台"
      all-label="全部平台"
      :model-value="modelValue.platforms"
      :options="platformOptions"
      :disabled="loading"
      @update:model-value="updateArray('platforms', $event)"
    />
    <WorkbenchMultiSelect
      label="品牌"
      :model-value="modelValue.brandIds"
      :options="brandOptions"
      :disabled="loading"
      @update:model-value="updateArray('brandIds', $event)"
    />
    <WorkbenchMultiSelect
      label="车型"
      :model-value="modelValue.vehicleModelIds"
      :options="vehicleOptions"
      :disabled="loading"
      @update:model-value="updateArray('vehicleModelIds', $event)"
    />
    <WorkbenchMultiSelect
      label="发声"
      :model-value="modelValue.voiceTypes"
      :options="voiceTypeOptions"
      :disabled="loading"
      @update:model-value="updateArray('voiceTypes', $event)"
    />
    <WorkbenchMultiSelect
      label="一级标签"
      :model-value="modelValue.primaryLabels"
      :options="primaryLabelOptions"
      :disabled="loading"
      @update:model-value="updateArray('primaryLabels', $event)"
    />
    <WorkbenchMultiSelect
      label="二级标签"
      :model-value="modelValue.secondaryLabels"
      :options="secondaryLabelOptions"
      :disabled="loading"
      @update:model-value="updateArray('secondaryLabels', $event)"
    />
    <AimaDateRange
      class="workbench-date"
      label="工作台时间范围"
      :from="modelValue.dateFrom"
      :to="modelValue.dateTo"
      @update:from="updateDate('dateFrom', $event)"
      @update:to="updateDate('dateTo', $event)"
    />
    <button
      class="reset"
      type="button"
      @click="emit('reset')"
    >
      重置
    </button>
  </div>
</template>

<style scoped>
.workbench-filters {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding: 6px 8px;
  border: 1px solid var(--aima-border);
  border-radius: 7px;
  background: #fef7ff;
  overscroll-behavior-inline: contain;
  scrollbar-width: thin;
}
.workbench-filters > * { flex: none; }
.workbench-date { width: 205px; }
.workbench-date :deep(.date-trigger) { height: 30px; border-radius: 6px; font-size: 11px; }
.reset { height: 30px; padding: 0 8px; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
</style>
