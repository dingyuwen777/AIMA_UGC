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
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WorkbenchFilters]
  'update:date': [value: WorkbenchFilters]
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
const secondaryLabelOptions = computed<WorkbenchSelectOption[]>(() => {
  const selected = new Set(props.modelValue.primaryLabels)
  const options = new Map<string, WorkbenchSelectOption>()
  for (const item of props.taxonomy?.labels ?? []) {
    if (selected.size > 0 && !selected.has(item.primary_label)) continue
    for (const value of item.secondary_labels) {
      if (!options.has(value)) {
        options.set(value, { value, label: `${item.primary_label} / ${value}` })
      }
    }
  }
  return [...options.values()]
})
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

/** 一级标签变化时只保留仍属于所选父级的二级标签。 */
function updatePrimaryLabels(value: string[]): void {
  const selected = new Set(value)
  const allowed = new Set(
    (props.taxonomy?.labels ?? [])
      .filter((item) => selected.size === 0 || selected.has(item.primary_label))
      .flatMap((item) => item.secondary_labels),
  )
  emit('update:modelValue', {
    ...props.modelValue,
    primaryLabels: [...value],
    secondaryLabels: props.modelValue.secondaryLabels.filter((item) => allowed.has(item)),
  })
}

/** 一次性写回日期对，防止两个同步事件各自读取旧 props 覆盖另一个端点。 */
function updateDateRange(value: { from: string; to: string }): void {
  emit('update:date', {
    ...props.modelValue,
    dateFrom: value.from,
    dateTo: value.to,
  })
}
</script>

<template>
  <div class="workbench-filters">
    <WorkbenchMultiSelect
      label="情感"
      :model-value="modelValue.sentiments"
      :options="sentimentOptions"
      @update:model-value="updateArray('sentiments', $event)"
    />
    <WorkbenchMultiSelect
      label="平台"
      all-label="全部平台"
      :model-value="modelValue.platforms"
      :options="platformOptions"
      @update:model-value="updateArray('platforms', $event)"
    />
    <WorkbenchMultiSelect
      label="品牌"
      :model-value="modelValue.brandIds"
      :options="brandOptions"
      @update:model-value="updateArray('brandIds', $event)"
    />
    <WorkbenchMultiSelect
      label="车型"
      :model-value="modelValue.vehicleModelIds"
      :options="vehicleOptions"
      @update:model-value="updateArray('vehicleModelIds', $event)"
    />
    <WorkbenchMultiSelect
      label="发声"
      :model-value="modelValue.voiceTypes"
      :options="voiceTypeOptions"
      @update:model-value="updateArray('voiceTypes', $event)"
    />
    <WorkbenchMultiSelect
      label="一级标签"
      :model-value="modelValue.primaryLabels"
      :options="primaryLabelOptions"
      @update:model-value="updatePrimaryLabels"
    />
    <WorkbenchMultiSelect
      label="二级标签"
      :model-value="modelValue.secondaryLabels"
      :options="secondaryLabelOptions"
      @update:model-value="updateArray('secondaryLabels', $event)"
    />
    <AimaDateRange
      class="workbench-date"
      label="工作台时间范围"
      :from="modelValue.dateFrom"
      :to="modelValue.dateTo"
      @update:range="updateDateRange"
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
