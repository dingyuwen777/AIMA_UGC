<script setup lang="ts">
import { computed } from 'vue'

import {
  ContentAnalysisStatus,
  ContentRelevance,
  PlatformName,
  type ContentFilterOptionsResponse,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDateRange from '../../../../../shared/ui/AimaDateRange.vue'
import AimaMultiSelect, { type AimaSelectOption } from '../../../../../shared/ui/AimaMultiSelect.vue'
import BrandMultiSelect from '../../../../../shared/BrandMultiSelect.vue'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import { useVehicleCatalogStore } from '../../../../../shared/domain/vehicleCatalog'
import {
  analysisStatusLabel,
  platformLabel,
  relevanceLabel,
} from '../../../format'
import type { LegacyLabelCompatibility, LegacyVehicleCompatibility } from '../../../store'

const props = withDefaults(defineProps<{
  search: string
  platform: '' | PlatformName
  platforms?: PlatformName[]
  analysisStatus: '' | ContentAnalysisStatus
  relevance: '' | ContentRelevance
  voiceType: string
  sentiment: string
  sentiments?: string[]
  voiceTypes?: string[]
  primaryLabels?: string[]
  secondaryLabels?: string[]
  publishedFrom: string
  publishedTo: string
  sourceIdentifier: string
  brandIds?: string[]
  vehicleModelIds?: string[]
  filterOptions: ContentFilterOptionsResponse | null
  filterOptionsLoading: boolean
  legacyLabelCompatibility?: LegacyLabelCompatibility | null
  legacyVehicleCompatibility?: LegacyVehicleCompatibility | null
}>(), {
  brandIds: () => [],
  vehicleModelIds: () => [],
  primaryLabels: () => [],
  secondaryLabels: () => [],
  legacyLabelCompatibility: null,
  legacyVehicleCompatibility: null,
  platforms: () => [],
  sentiments: () => [],
  voiceTypes: () => [],
})

const emit = defineEmits<{
  'update:search': [value: string]
  'update:platform': [value: '' | PlatformName]
  'update:platforms': [value: PlatformName[]]
  'update:analysisStatus': [value: '' | ContentAnalysisStatus]
  'update:relevance': [value: '' | ContentRelevance]
  'update:voiceType': [value: string]
  'update:sentiment': [value: string]
  'update:sentiments': [value: string[]]
  'update:voiceTypes': [value: string[]]
  'update:primaryLabels': [value: string[]]
  'update:secondaryLabels': [value: string[]]
  'update:publishedFrom': [value: string]
  'update:publishedTo': [value: string]
  'update:sourceIdentifier': [value: string]
  'update:brandIds': [value: string[]]
  'update:vehicleModelIds': [value: string[]]
  search: []
  reset: []
}>()

const labelOptionsDisabled = computed(() => !props.filterOptions)
const vehicleOptionsDisabled = computed(() => props.brandIds.length === 0)
const vehicleDisabledHint = computed(() => {
  if (props.legacyVehicleCompatibility?.vehicleModelIds.length && props.brandIds.length === 0) {
    return `已选 ${props.legacyVehicleCompatibility.vehicleModelIds.length} 款车型（旧版兼容）`
  }
  return '请先选择品牌'
})
const catalog = useVehicleCatalogStore()

/** 品牌确认是用户动作；目录未就绪时不提前清空未知车型，目录就绪后收敛到当前品牌。 */
function updateBrands(ids: string[]): void {
  emit('update:brandIds', ids)
  if (!ids.length) {
    emit('update:vehicleModelIds', [])
    return
  }
  if (catalog.vehicles.active === null) return
  emit('update:vehicleModelIds', props.vehicleModelIds.filter((id) => {
    const vehicle = catalog.knownVehicles[id]
    return Boolean(vehicle && vehicle.brand_id != null && ids.includes(vehicle.brand_id))
  }))
}
const secondaryOptionsDisabled = computed(
  () => labelOptionsDisabled.value || props.primaryLabels.length === 0,
)
const primaryLabelOptions = computed<AimaSelectOption[]>(() =>
  (props.filterOptions?.labels ?? []).map((item) => ({
    value: item.primary_label,
    label: optionLabel(item.primary_label, item.source),
  })),
)
const secondaryLabelOptions = computed(() => {
  const selectedPrimaryLabels = new Set(props.primaryLabels)
  const result = new Map<string, { value: string, label: string, source: 'active' | 'historical' }>()
  for (const group of props.filterOptions?.labels ?? []) {
    if (!selectedPrimaryLabels.has(group.primary_label)) continue
    for (const item of group.secondary_labels) {
      if (!result.has(item.value)) {
        result.set(item.value, {
          value: item.value,
          label: props.primaryLabels.length > 1
            ? `${group.primary_label} / ${optionLabel(item.value, item.source)}`
            : optionLabel(item.value, item.source),
          source: item.source,
        })
      }
    }
  }
  return [...result.values()]
})
const primaryLabelSummary = computed(() => {
  if (props.filterOptionsLoading && !props.filterOptions) return '筛选项加载中'
  if (!props.filterOptions) return '筛选项暂不可用'
  return props.primaryLabels.length ? `已选 ${props.primaryLabels.length} 个一级标签` : '全部一级标签'
})
const secondaryLabelSummary = computed(() => {
  if (secondaryOptionsDisabled.value) return props.primaryLabels.length ? '筛选项暂不可用' : '请先选择一级标签'
  return props.secondaryLabels.length ? `已选 ${props.secondaryLabels.length} 个二级标签` : '全部二级标签'
})
const legacyLabelCompatibilityText = computed(() => {
  const legacy = props.legacyLabelCompatibility
  if (!legacy) return ''
  const conditions: string[] = []
  if (legacy.primaryLabels.length) {
    conditions.push(`一级「${legacy.primaryLabels.join('、')}」`)
  }
  if (legacy.secondaryLabels.length) {
    conditions.push(`二级「${legacy.secondaryLabels.join('、')}」`)
  }
  return `当前保留旧版兼容筛选：${conditions.join(' AND ')}。该组合继续按原查询语义生效；重新选择标签并查询后切换到当前层级规则。`
})
const legacyVehicleCompatibilityText = computed(() => {
  const legacy = props.legacyVehicleCompatibility
  if (!legacy) return ''
  const conditions: string[] = []
  if (legacy.brandIds.length) {
    const brands = legacy.brandIds.map((id) => catalog.knownBrands[id]?.display_name ?? id).join('、')
    conditions.push(`品牌「${brands}」`)
  }
  if (legacy.vehicleModelIds.length) {
    const vehicles = legacy.vehicleModelIds.map((id) => catalog.knownVehicles[id]?.display_name ?? id).join('、')
    conditions.push(`车型「${vehicles}」`)
  }
  if (!conditions.length) return ''
  return `当前保留旧版品牌/车型兼容筛选：${conditions.join(' AND ')}。该组合继续按原查询语义生效；重新选择品牌或车型并查询后切换到当前层级规则。`
})
const platformOptions = Object.values(PlatformName)
const relevanceOptions = Object.values(ContentRelevance)
const analysisStatusOptions = Object.values(ContentAnalysisStatus)
const platformSelectOptions = computed<AimaSelectOption[]>(() =>
  platformOptions.map((item) => ({ value: item, label: platformLabel(item) })),
)
const sentimentSelectOptions = computed<AimaSelectOption[]>(() =>
  (props.filterOptions?.sentiments ?? []).map((item) => ({
    value: item.value,
    label: optionLabel(item.value, item.source),
  })),
)
const voiceTypeSelectOptions = computed<AimaSelectOption[]>(() =>
  (props.filterOptions?.voice_types ?? []).map((item) => ({
    value: item.value,
    label: optionLabel(item.value, item.source),
  })),
)

/** 多选只写复数数组；旧单数字段仅用于旧链接/旧会话恢复时的回显。 */
const platformDisplay = computed<PlatformName[]>(() =>
  props.platforms.length ? props.platforms : props.platform ? [props.platform] : [],
)
const sentimentDisplay = computed<string[]>(() =>
  props.sentiments.length ? props.sentiments : props.sentiment ? [props.sentiment] : [],
)
const voiceTypeDisplay = computed<string[]>(() =>
  props.voiceTypes.length ? props.voiceTypes : props.voiceType ? [props.voiceType] : [],
)
const sentimentPlaceholder = computed(() => {
  if (props.filterOptionsLoading && !props.filterOptions) return '筛选项加载中'
  if (!props.filterOptions) return '筛选项暂不可用'
  return '全部情感'
})
const voiceTypePlaceholder = computed(() => {
  if (props.filterOptionsLoading && !props.filterOptions) return '筛选项加载中'
  if (!props.filterOptions) return '筛选项暂不可用'
  return '全部发声类型'
})

function updatePlatformSelection(value: string[]): void {
  emit('update:platform', '')
  emit('update:platforms', value.filter((item): item is PlatformName =>
    Object.values(PlatformName).includes(item as PlatformName),
  ))
}
function updateSentimentSelection(value: string[]): void {
  emit('update:sentiment', '')
  emit('update:sentiments', value)
}
function updateVoiceTypeSelection(value: string[]): void {
  emit('update:voiceType', '')
  emit('update:voiceTypes', value)
}

function optionLabel(value: string, source: 'active' | 'historical'): string {
  return source === 'historical' ? `${value}（历史数据）` : value
}

/** 从原生输入控件事件中读取字符串值，保持页面与 Store 的 v-model 边界单一。 */
function value(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value
}

/** 一级集合变化时同步剔除不再属于任何已选父级的二级值，隐藏值不能继续参与查询。 */
function updatePrimaryLabels(primaryLabels: string[]): void {
  const available = new Set((props.filterOptions?.labels ?? []).map((item) => item.primary_label))
  const next = [...new Set(primaryLabels.filter((item) => available.has(item)))]
  const allowedSecondaryLabels = new Set(
    (props.filterOptions?.labels ?? [])
      .filter((item) => next.includes(item.primary_label))
      .flatMap((item) => item.secondary_labels.map((label) => label.value)),
  )
  emit('update:primaryLabels', next)
  emit(
    'update:secondaryLabels',
    props.secondaryLabels.filter((value) => allowedSecondaryLabels.has(value)),
  )
}

/** 二级集合只接受当前一级选择允许的值，避免隐藏条件进入查询。 */
function updateSecondaryLabels(secondaryLabels: string[]): void {
  if (secondaryOptionsDisabled.value) return
  const allowed = new Set(secondaryLabelOptions.value.map((item) => item.value))
  emit(
    'update:secondaryLabels',
    [...new Set(secondaryLabels.filter((item) => allowed.has(item)))],
  )
}

</script>

<template>
  <section
    class="filters"
    aria-label="声音广场筛选条件"
  >
    <div class="filter-row filter-row--primary">
      <label class="field field--search"><span>搜索内容</span><input
        :value="search"
        placeholder="搜索标题、正文或作者"
        @input="emit('update:search', value($event))"
        @keyup.enter="emit('search')"
      ></label>
      <AimaMultiSelect
        class="field field--platform"
        appearance="field"
        label="平台"
        :model-value="platformDisplay"
        :options="platformSelectOptions"
        all-label="全部平台"
        @update:model-value="updatePlatformSelection"
      />
      <label class="field field--relevance"><span>相关性</span><select
        aria-label="相关性"
        :value="relevance"
        @change="emit('update:relevance', value($event) as '' | ContentRelevance)"
      ><option value="">默认业务数据</option><option
        v-for="item in relevanceOptions"
        :key="item"
        :value="item"
      >{{ relevanceLabel(item) }}</option></select></label>
      <AimaMultiSelect
        class="field field--sentiment"
        appearance="field"
        label="情感"
        :model-value="sentimentDisplay"
        :options="sentimentSelectOptions"
        :all-label="sentimentPlaceholder"
        :disabled="!filterOptions"
        @update:model-value="updateSentimentSelection"
      />
      <label class="field field--status"><span>状态</span><select
        aria-label="状态"
        :value="analysisStatus"
        @change="emit('update:analysisStatus', value($event) as '' | ContentAnalysisStatus)"
      ><option value="">全部状态</option><option
        v-for="item in analysisStatusOptions"
        :key="item"
        :value="item"
      >{{ analysisStatusLabel(item) }}</option></select></label>
      <div class="field field--date">
        <span>发布时间范围</span><AimaDateRange
          :from="publishedFrom"
          :to="publishedTo"
          @update:from="emit('update:publishedFrom', $event)"
          @update:to="emit('update:publishedTo', $event)"
        />
      </div>
    </div>

    <p class="filter-hint">
      可与平台、品牌、车型、AI 分析结果和发布时间组合筛选
    </p>

    <div class="filter-row filter-row--secondary">
      <BrandMultiSelect
        :model-value="brandIds"
        compact
        label="品牌"
        @update:model-value="updateBrands"
      />
      <VehicleMultiSelect
        :model-value="vehicleModelIds"
        :brand-ids="brandIds"
        compact
        label="车型"
        :disabled="vehicleOptionsDisabled"
        :disabled-hint="vehicleDisabledHint"
        @update:model-value="emit('update:vehicleModelIds', $event)"
      />
      <AimaMultiSelect
        class="field field--voice-type"
        appearance="field"
        label="发声类型"
        :model-value="voiceTypeDisplay"
        :options="voiceTypeSelectOptions"
        :all-label="voiceTypePlaceholder"
        :disabled="!filterOptions"
        @update:model-value="updateVoiceTypeSelection"
      />
    </div>

    <div class="filter-row filter-row--tertiary">
      <AimaMultiSelect
        class="field field--label"
        appearance="field"
        label="一级标签"
        :model-value="primaryLabels"
        :options="primaryLabelOptions"
        :summary="primaryLabelSummary"
        :disabled="labelOptionsDisabled"
        :show-bulk-action="false"
        @update:model-value="updatePrimaryLabels"
      />
      <AimaMultiSelect
        class="field field--label"
        appearance="field"
        label="二级标签"
        :model-value="secondaryLabels"
        :options="secondaryLabelOptions"
        :summary="secondaryLabelSummary"
        :disabled="secondaryOptionsDisabled"
        :show-bulk-action="false"
        @update:model-value="updateSecondaryLabels"
      />
    </div>

    <p
      v-if="legacyLabelCompatibilityText"
      class="legacy-label-warning"
      role="status"
    >
      {{ legacyLabelCompatibilityText }}
    </p>

    <p
      v-if="legacyVehicleCompatibilityText"
      class="legacy-label-warning"
      role="status"
    >
      {{ legacyVehicleCompatibilityText }}
    </p>

    <footer class="filter-footer">
      <div class="filter-summary">
        <span>当前条件：</span><span class="filter-chip filter-chip--primary">{{ platforms.length ? platforms.map(platformLabel).join('、') : platform ? platformLabel(platform) : '全部平台' }}</span><span class="filter-chip">{{ sentiments.length ? sentiments.join('、') : sentiment || '全部情感' }}</span><span class="filter-chip">{{ voiceTypes.length ? voiceTypes.join('、') : voiceType || '全部发声类型' }}</span><span class="filter-chip">{{ brandIds.length ? `已选 ${brandIds.length} 个品牌` : '全部品牌' }}</span><span class="filter-chip">{{ vehicleModelIds.length ? `已选 ${vehicleModelIds.length} 款车型` : '全部车型' }}</span><span class="filter-chip">{{ primaryLabels.length ? `已选 ${primaryLabels.length} 个一级标签` : '全部一级标签' }}</span><span class="filter-chip">{{ secondaryLabels.length ? `已选 ${secondaryLabels.length} 个二级标签` : '全部二级标签' }}</span><button
          v-if="sourceIdentifier"
          class="filter-chip"
          type="button"
          aria-label="清除来源筛选"
          @click="emit('update:sourceIdentifier', '')"
        >
          指定来源 ×
        </button>
      </div>
      <div class="filter-actions">
        <AimaButton
          size="small"
          @click="emit('reset')"
        >
          条件重置
        </AimaButton><AimaButton
          variant="primary"
          size="small"
          @click="emit('search')"
        >
          查询
        </AimaButton>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.filters { display: grid; min-width: 0; gap: 12px; padding: 20px; border: 0; border-radius: 8px; background: var(--aima-surface); box-shadow: inset 0 0 0 1px var(--aima-border); }
.filter-row { display: flex; min-width: 0; flex-wrap: wrap; align-items: flex-start; gap: 12px 16px; }
.filter-row--primary .field--search { min-width: 280px; flex: 1 1 280px; }
.filter-row--primary .field--platform { flex: 0 0 140px; }
.filter-row--primary .field--relevance { flex: 0 0 150px; }
.filter-row--primary .field--sentiment { flex: 0 0 120px; }
.filter-row--primary .field--status { flex: 0 0 130px; }
.filter-row--primary .field--date { flex: 0 0 200px; }
.filter-row--secondary > :nth-child(1),
.filter-row--secondary > :nth-child(2) { min-width: 180px; flex: 0 0 180px; }
.filter-row--secondary > .field--voice-type { min-width: 160px; flex: 0 0 160px; }
.filter-row--tertiary > .field { min-width: 180px; flex: 1 1 180px; }
.field { display: grid; min-width: 0; gap: 6px; color: var(--aima-text-muted); font-size: 12px; font-weight: 700; }
.field input, .field select { width: 100%; height: 40px; min-width: 0; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; color: var(--aima-text-muted); background: var(--aima-surface); font: inherit; font-size: 13px; font-weight: 400; }
.field input::placeholder { color: var(--aima-text-disabled); }
.field select:disabled { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); cursor: not-allowed; }
.field input:focus-visible, .field select:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 1px; }
.filter-hint { display: none; margin: 0; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
.legacy-label-warning { margin: 0; padding: 8px 10px; border-radius: 6px; color: var(--aima-text-muted); background: var(--aima-primary-soft); box-shadow: inset 0 0 0 1px var(--aima-border); font-size: 12px; line-height: 18px; }
.filter-footer { display: flex; min-width: 0; min-height: 45px; align-items: flex-end; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--aima-border); }
.filter-summary { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--aima-text-muted); font-size: 12px; }
.filter-chip { max-width: 100%; padding: 4px 10px; border: 0; border-radius: 4px; color: var(--aima-text-muted); background: var(--aima-color-bg-hover); font: inherit; overflow-wrap: anywhere; }
.filter-chip--primary { color: var(--aima-primary); background: var(--aima-primary-soft); }
.filter-actions { display: flex; flex: none; gap: 12px; }
.filter-actions :deep(.aima-button) { min-height: 32px; padding-inline: 16px; border-radius: 4px; font-size: 13px; }
@media (max-width: 1279px) {
  .filter-hint { display: block; }
  .filter-footer { align-items: flex-start; flex-wrap: wrap; }
}
@media (max-width: 900px) {
  .filter-row--primary > .field,
  .filter-row--secondary > :nth-child(n),
  .filter-row--tertiary > .field { min-width: min(100%, 180px); flex: 1 1 calc(50% - 8px); }
  .filter-row--primary .field--search,
  .filter-row--primary .field--date { flex-basis: 100%; }
}
</style>
