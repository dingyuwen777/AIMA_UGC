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
import BrandMultiSelect from '../../../../../shared/BrandMultiSelect.vue'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import {
  analysisStatusLabel,
  platformLabel,
  relevanceLabel,
} from '../../../format'
import type { LegacyLabelCompatibility } from '../../../store'

const props = withDefaults(defineProps<{
  search: string
  platforms: PlatformName[]
  analysisStatus: '' | ContentAnalysisStatus
  relevance: '' | ContentRelevance
  voiceTypes: string[]
  sentiments: string[]
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
}>(), {
  brandIds: () => [],
  vehicleModelIds: () => [],
  primaryLabels: () => [],
  secondaryLabels: () => [],
  legacyLabelCompatibility: null,
})

const emit = defineEmits<{
  'update:search': [value: string]
  'update:platforms': [value: PlatformName[]]
  'update:analysisStatus': [value: '' | ContentAnalysisStatus]
  'update:relevance': [value: '' | ContentRelevance]
  'update:voiceTypes': [value: string[]]
  'update:sentiments': [value: string[]]
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

const labelOptionsDisabled = computed(() => props.filterOptionsLoading || !props.filterOptions)
const secondaryOptionsDisabled = computed(
  () => labelOptionsDisabled.value || props.primaryLabels.length === 0,
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
  if (props.filterOptionsLoading) return '筛选项加载中'
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
const platformOptions = Object.values(PlatformName)
const relevanceOptions = Object.values(ContentRelevance)
const platformsSummary = computed(() => {
  if (!props.platforms.length) return '全部平台'
  if (props.platforms.length === 1) return platformLabel(props.platforms[0])
  return `已选 ${props.platforms.length} 个平台`
})

function togglePlatform(platform: PlatformName): void {
  const next = props.platforms.includes(platform)
    ? props.platforms.filter((item) => item !== platform)
    : [...props.platforms, platform]
  emit('update:platforms', next)
}
const sentimentSummary = computed(() => {
  if (!props.filterOptions) return '筛选项暂不可用'
  if (!props.sentiments.length) return '全部情感'
  if (props.sentiments.length === 1) return props.sentiments[0]
  return `已选 ${props.sentiments.length} 个情感`
})
const voiceTypeSummary = computed(() => {
  if (!props.filterOptions) return '筛选项暂不可用'
  if (!props.voiceTypes.length) return '全部发声类型'
  if (props.voiceTypes.length === 1) return props.voiceTypes[0]
  return `已选 ${props.voiceTypes.length} 个发声类型`
})

function toggleSentiment(value: string): void {
  const next = props.sentiments.includes(value)
    ? props.sentiments.filter((item) => item !== value)
    : [...props.sentiments, value]
  emit('update:sentiments', next)
}
function toggleVoiceType(value: string): void {
  const next = props.voiceTypes.includes(value)
    ? props.voiceTypes.filter((item) => item !== value)
    : [...props.voiceTypes, value]
  emit('update:voiceTypes', next)
}
const analysisStatusOptions = Object.values(ContentAnalysisStatus)

function optionLabel(value: string, source: 'active' | 'historical'): string {
  return source === 'historical' ? `${value}（历史数据）` : value
}

/** 从原生输入控件事件中读取字符串值，保持页面与 Store 的 v-model 边界单一。 */
function value(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value
}

/** 一级变化时同步剔除不再属于任何已选父级的二级值，隐藏值不能继续参与查询。 */
function togglePrimaryLabel(primaryLabel: string): void {
  const next = new Set(props.primaryLabels)
  if (next.has(primaryLabel)) next.delete(primaryLabel)
  else next.add(primaryLabel)
  const allowedSecondaryLabels = new Set(
    (props.filterOptions?.labels ?? [])
      .filter((item) => next.has(item.primary_label))
      .flatMap((item) => item.secondary_labels.map((label) => label.value)),
  )
  emit('update:primaryLabels', [...next])
  emit(
    'update:secondaryLabels',
    props.secondaryLabels.filter((value) => allowedSecondaryLabels.has(value)),
  )
}

function toggleSecondaryLabel(secondaryLabel: string): void {
  if (secondaryOptionsDisabled.value) return
  const allowed = new Set(secondaryLabelOptions.value.map((item) => item.value))
  if (!allowed.has(secondaryLabel)) return
  const next = new Set(props.secondaryLabels)
  if (next.has(secondaryLabel)) next.delete(secondaryLabel)
  else next.add(secondaryLabel)
  emit('update:secondaryLabels', [...next])
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
      <div class="field field--platform">
        <span>平台</span>
        <details class="multi-select">
          <summary aria-label="平台">
            <span>{{ platformsSummary }}</span>
            <span aria-hidden="true">⌄</span>
          </summary>
          <div class="multi-select__options">
            <label
              v-for="item in platformOptions"
              :key="item"
            >
              <input
                type="checkbox"
                :checked="platforms.includes(item)"
                @change="togglePlatform(item)"
              >
              <span>{{ platformLabel(item) }}</span>
            </label>
          </div>
        </details>
      </div>
      <label class="field field--relevance"><span>相关性</span><select
        aria-label="相关性"
        :value="relevance"
        @change="emit('update:relevance', value($event) as '' | ContentRelevance)"
      ><option value="">默认业务数据</option><option
        v-for="item in relevanceOptions"
        :key="item"
        :value="item"
      >{{ relevanceLabel(item) }}</option></select></label>
      <div class="field field--sentiment">
        <span>情感</span>
        <details class="multi-select">
          <summary aria-label="情感">
            <span>{{ sentimentSummary }}</span>
            <span aria-hidden="true">⌄</span>
          </summary>
          <div class="multi-select__options">
            <label
              v-for="item in filterOptions?.sentiments ?? []"
              :key="item.value"
            >
              <input
                type="checkbox"
                :checked="sentiments.includes(item.value)"
                :disabled="filterOptionsLoading || !filterOptions"
                @change="toggleSentiment(item.value)"
              >
              <span>{{ optionLabel(item.value, item.source) }}</span>
            </label>
          </div>
        </details>
      </div>
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
        @update:model-value="emit('update:brandIds', $event)"
      />
      <VehicleMultiSelect
        :model-value="vehicleModelIds"
        compact
        label="车型"
        @update:model-value="emit('update:vehicleModelIds', $event)"
      />
      <div class="field field--voice-type">
        <span>发声类型</span>
        <details class="multi-select">
          <summary aria-label="发声类型">
            <span>{{ voiceTypeSummary }}</span>
            <span aria-hidden="true">⌄</span>
          </summary>
          <div class="multi-select__options">
            <label
              v-for="item in filterOptions?.voice_types ?? []"
              :key="item.value"
            >
              <input
                type="checkbox"
                :checked="voiceTypes.includes(item.value)"
                :disabled="filterOptionsLoading || !filterOptions"
                @change="toggleVoiceType(item.value)"
              >
              <span>{{ optionLabel(item.value, item.source) }}</span>
            </label>
          </div>
        </details>
      </div>
    </div>

    <div class="filter-row filter-row--tertiary">
      <div class="field field--label">
        <span>一级标签</span><details
          class="multi-select"
          :class="{ 'multi-select--disabled': labelOptionsDisabled }"
          @click="labelOptionsDisabled && $event.preventDefault()"
        >
          <summary
            aria-label="一级标签"
            :aria-disabled="labelOptionsDisabled"
          >
            {{ primaryLabelSummary }}
          </summary><label
            v-for="item in filterOptions?.labels ?? []"
            :key="item.primary_label"
          ><input
            type="checkbox"
            :checked="primaryLabels.includes(item.primary_label)"
            :disabled="labelOptionsDisabled"
            @change="togglePrimaryLabel(item.primary_label)"
          >{{ optionLabel(item.primary_label, item.source) }}</label>
        </details>
      </div>
      <div class="field field--label">
        <span>二级标签</span><details
          class="multi-select"
          :class="{ 'multi-select--disabled': secondaryOptionsDisabled }"
          @click="secondaryOptionsDisabled && $event.preventDefault()"
        >
          <summary
            aria-label="二级标签"
            :aria-disabled="secondaryOptionsDisabled"
          >
            {{ secondaryLabelSummary }}
          </summary><label
            v-for="item in secondaryLabelOptions"
            :key="item.value"
          ><input
            type="checkbox"
            :checked="secondaryLabels.includes(item.value)"
            :disabled="secondaryOptionsDisabled"
            @change="toggleSecondaryLabel(item.value)"
          >{{ item.label }}</label>
        </details>
      </div>
    </div>

    <p
      v-if="legacyLabelCompatibilityText"
      class="legacy-label-warning"
      role="status"
    >
      {{ legacyLabelCompatibilityText }}
    </p>

    <footer class="filter-footer">
      <div class="filter-summary">
        <span>当前条件：</span><span class="filter-chip">{{ platformsSummary }}</span><span class="filter-chip">{{ brandIds.length ? `已选 ${brandIds.length} 个品牌` : '全部品牌' }}</span><span class="filter-chip">{{ vehicleModelIds.length ? `已选 ${vehicleModelIds.length} 款车型` : '全部车型' }}</span><span class="filter-chip">{{ primaryLabels.length ? `已选 ${primaryLabels.length} 个一级标签` : '全部一级标签' }}</span><span class="filter-chip">{{ secondaryLabels.length ? `已选 ${secondaryLabels.length} 个二级标签` : '全部二级标签' }}</span><button
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
.filter-row--primary .field--platform { flex: 0 0 180px; }
.filter-row--primary .field--relevance { flex: 0 0 150px; }
.filter-row--primary .field--sentiment { flex: 0 0 120px; }
.filter-row--primary .field--status { flex: 0 0 130px; }
.filter-row--primary .field--date { flex: 0 0 200px; }
.filter-row--secondary > :nth-child(1),
.filter-row--secondary > :nth-child(2) { min-width: 180px; flex: 0 0 180px; }
.filter-row--secondary > :nth-child(3) { min-width: 160px; flex: 0 0 160px; }
.filter-row--tertiary > .field { min-width: 180px; flex: 1 1 180px; }
.field { display: grid; min-width: 0; gap: 6px; color: var(--aima-text-muted); font-size: 12px; font-weight: 700; }
.field input, .field select { width: 100%; height: 40px; min-width: 0; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; color: var(--aima-text-muted); background: var(--aima-surface); font: inherit; font-size: 13px; font-weight: 400; }
.field input::placeholder { color: var(--aima-text-disabled); }
.field select:disabled { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); cursor: not-allowed; }
.field input:focus-visible, .field select:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 1px; }
.multi-select { position: relative; min-width: 0; border: 1px solid var(--aima-border-strong); border-radius: 8px; background: var(--aima-surface); font-size: 13px; font-weight: 400; }
.multi-select summary { display: flex; height: 38px; align-items: center; justify-content: space-between; gap: 6px; padding: 0 12px; overflow: hidden; cursor: pointer; list-style: none; }
.multi-select summary::-webkit-details-marker { display: none; }
.multi-select summary > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.multi-select[open] { z-index: 5; }
.multi-select__options { position: absolute; top: 100%; left: -1px; right: -1px; z-index: 5; display: grid; max-height: 220px; overflow: auto; border: 1px solid var(--aima-border); border-top: 0; border-radius: 0 0 8px 8px; background: var(--aima-surface); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
.multi-select__options label { display: flex; width: 100%; align-items: center; gap: 7px; padding: 8px 12px; cursor: pointer; }
.multi-select__options label:hover { background: var(--aima-color-bg-hover); }
.multi-select__options input { width: 14px; height: 14px; margin: 0; accent-color: var(--aima-primary); }
.multi-select label { display: flex; width: 100%; align-items: center; gap: 7px; padding: 8px 12px; border-inline: 1px solid var(--aima-border); background: #fff; }
.multi-select label:last-child { border-bottom: 1px solid var(--aima-border); border-radius: 0 0 8px 8px; }
.multi-select input { width: 14px; height: 14px; }
.filter-row--tertiary .multi-select[open] { height: auto; max-height: 260px; overflow-y: auto; }
.multi-select--disabled { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); }
.multi-select--disabled summary { cursor: not-allowed; }
.filter-hint { display: none; margin: 0; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
.legacy-label-warning { margin: 0; padding: 8px 10px; border-radius: 6px; color: var(--aima-text-muted); background: var(--aima-primary-soft); box-shadow: inset 0 0 0 1px var(--aima-border); font-size: 12px; line-height: 18px; }
.filter-footer { display: flex; min-width: 0; min-height: 45px; align-items: flex-end; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--aima-border); }
.filter-summary { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--aima-text-muted); font-size: 12px; }
.filter-chip { max-width: 100%; padding: 4px 10px; border: 0; border-radius: 4px; color: var(--aima-text-muted); background: var(--aima-color-bg-hover); font: inherit; overflow-wrap: anywhere; }
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
