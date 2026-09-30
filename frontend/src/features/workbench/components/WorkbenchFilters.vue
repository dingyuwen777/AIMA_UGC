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
import AimaMultiSelect, { type AimaSelectOption } from '../../../shared/ui/AimaMultiSelect.vue'
import type { WorkbenchFilters } from '../store'

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

const platformOptions = computed<AimaSelectOption[]>(() =>
  Object.values(PlatformName).map((value) => ({ value, label: platformLabel(value) })),
)
const sentimentOptions = computed<AimaSelectOption[]>(() =>
  (props.taxonomy?.sentiments ?? []).map((value) => ({ value, label: value })),
)
const voiceTypeOptions = computed<AimaSelectOption[]>(() =>
  (props.taxonomy?.voice_types ?? []).map((value) => ({ value, label: value })),
)
const primaryLabelOptions = computed<AimaSelectOption[]>(() =>
  (props.taxonomy?.labels ?? []).map((item) => ({
    value: item.primary_label,
    label: item.primary_label,
  })),
)
const secondaryLabelOptions = computed<AimaSelectOption[]>(() => {
  const selectedPrimaryLabels = new Set(props.modelValue.primaryLabels)
  return (props.taxonomy?.labels ?? [])
    .filter((item) => selectedPrimaryLabels.has(item.primary_label))
    .flatMap((item) =>
      item.secondary_labels.map((value) => ({
        value,
        label: `${item.primary_label} / ${value}`,
      })),
    )
})
const brandOptions = computed<AimaSelectOption[]>(() =>
  props.brands.map((item) => ({ value: item.id, label: item.display_name })),
)
const vehicleOptions = computed<AimaSelectOption[]>(() => {
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
    <AimaMultiSelect
      label="情感"
      :model-value="modelValue.sentiments"
      :options="sentimentOptions"
      @update:model-value="updateArray('sentiments', $event)"
    />
    <AimaMultiSelect
      label="平台"
      all-label="全部平台"
      :model-value="modelValue.platforms"
      :options="platformOptions"
      @update:model-value="updateArray('platforms', $event)"
    />
    <AimaMultiSelect
      label="品牌"
      :model-value="modelValue.brandIds"
      :options="brandOptions"
      @update:model-value="updateArray('brandIds', $event)"
    />
    <AimaMultiSelect
      label="车型"
      :model-value="modelValue.vehicleModelIds"
      :options="vehicleOptions"
      @update:model-value="updateArray('vehicleModelIds', $event)"
    />
    <AimaMultiSelect
      label="发声"
      :model-value="modelValue.voiceTypes"
      :options="voiceTypeOptions"
      @update:model-value="updateArray('voiceTypes', $event)"
    />
    <AimaMultiSelect
      label="一级标签"
      :model-value="modelValue.primaryLabels"
      :options="primaryLabelOptions"
      @update:model-value="updateArray('primaryLabels', $event)"
    />
    <AimaMultiSelect
      label="二级标签"
      :all-label="modelValue.primaryLabels.length ? '全部二级标签' : '请先选择一级标签'"
      :model-value="modelValue.secondaryLabels"
      :options="secondaryLabelOptions"
      :disabled="modelValue.primaryLabels.length === 0"
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
