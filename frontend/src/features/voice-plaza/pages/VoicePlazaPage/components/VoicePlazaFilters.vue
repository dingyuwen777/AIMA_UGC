<script setup lang="ts">
import { computed } from 'vue'

import type {
  ContentAnalysisStatus,
  ContentAnalysisTaxonomyResponse,
  ContentRelevance,
  PlatformName,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDateRange from '../../../../../shared/ui/AimaDateRange.vue'
import { platformLabel } from '../../../format'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'

const props = withDefaults(defineProps<{
  search: string
  platform: '' | PlatformName
  contentType: string
  analysisStatus: '' | ContentAnalysisStatus
  relevance: '' | ContentRelevance
  voiceType: string
  sentiment: string
  primaryLabel: string
  secondaryLabel: string
  publishedFrom: string
  publishedTo: string
  sourceIdentifier: string
  vehicleModelIds?: string[]
  taxonomy: ContentAnalysisTaxonomyResponse | null
  taxonomyLoading: boolean
}>(), { vehicleModelIds: () => [] })

const emit = defineEmits<{
  'update:search': [value: string]
  'update:platform': [value: '' | PlatformName]
  'update:contentType': [value: string]
  'update:analysisStatus': [value: '' | ContentAnalysisStatus]
  'update:relevance': [value: '' | ContentRelevance]
  'update:voiceType': [value: string]
  'update:sentiment': [value: string]
  'update:primaryLabel': [value: string]
  'update:secondaryLabel': [value: string]
  'update:publishedFrom': [value: string]
  'update:publishedTo': [value: string]
  'update:sourceIdentifier': [value: string]
  'update:vehicleModelIds': [value: string[]]
  search: []
  reset: []
}>()

const contentTypeOptions = [
  { value: 'image', label: '图文 / 图片' },
  { value: 'video', label: '视频' },
  { value: 'text', label: '纯文本' },
  { value: 'unknown', label: '未识别' },
] as const

const secondaryLabels = computed(
  () => props.taxonomy?.labels.find((item) => item.primary_label === props.primaryLabel)
    ?.secondary_labels ?? [],
)
/** 从原生输入控件事件中读取字符串值，保持页面与 Store 的 v-model 边界单一。 */
function value(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value
}

/** 一级标签变化时同时清空旧二级标签，避免提交不合法父子组合。 */
function updatePrimaryLabel(event: Event): void {
  emit('update:primaryLabel', value(event))
  emit('update:secondaryLabel', '')
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
        placeholder="搜索标题、正文、作者或内容 ID"
        @input="emit('update:search', value($event))"
        @keyup.enter="emit('search')"
      ></label>
      <label class="field field--platform"><span>平台</span><select
        aria-label="平台"
        :value="platform"
        @change="emit('update:platform', value($event) as '' | PlatformName)"
      ><option value="">全部平台</option><option value="xiaohongshu">小红书</option><option value="douyin">抖音</option><option value="weibo">微博</option><option value="bilibili">B站</option><option value="kuaishou">快手</option></select></label>
      <label class="field field--relevance"><span>相关性</span><select
        aria-label="相关性"
        :value="relevance"
        @change="emit('update:relevance', value($event) as '' | ContentRelevance)"
      ><option value="">默认业务数据</option><option value="relevant">相关</option><option value="irrelevant">不相关</option></select></label>
      <label class="field field--sentiment"><span>情感</span><select
        aria-label="情感"
        :value="sentiment"
        :disabled="taxonomyLoading || !taxonomy"
        @change="emit('update:sentiment', value($event))"
      ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部情感' : '分类配置暂不可用' }}</option><option
        v-for="item in taxonomy?.sentiments ?? []"
        :key="item"
        :value="item"
      >{{ item }}</option></select></label>
      <label class="field field--status"><span>状态</span><select
        aria-label="状态"
        :value="analysisStatus"
        @change="emit('update:analysisStatus', value($event) as '' | ContentAnalysisStatus)"
      ><option value="">全部状态</option><option value="completed">已分析</option><option value="pending">未分析</option><option value="stale">需重新分析</option></select></label>
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
      可与平台、车型、AI 分析结果和发布时间组合筛选
    </p>
    <div class="filter-row filter-row--secondary">
      <VehicleMultiSelect
        :model-value="vehicleModelIds"
        compact
        label="车型"
        @update:model-value="emit('update:vehicleModelIds', $event)"
      />
      <label class="field field--voice-type"><span>发声类型</span><select
        aria-label="发声类型"
        :value="voiceType"
        :disabled="taxonomyLoading || !taxonomy"
        @change="emit('update:voiceType', value($event))"
      ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部发声类型' : '分类配置暂不可用' }}</option><option
        v-for="item in taxonomy?.voice_types ?? []"
        :key="item"
        :value="item"
      >{{ item }}</option></select></label>
      <label class="field field--content-type"><span>内容类型</span><select
        aria-label="内容类型"
        :value="contentType"
        @change="emit('update:contentType', value($event))"
      ><option value="">全部类型</option><option
        v-for="item in contentTypeOptions"
        :key="item.value"
        :value="item.value"
      >{{ item.label }}</option></select></label>
      <label class="field field--label"><span>一级标签</span><select
        aria-label="一级标签"
        :value="primaryLabel"
        :disabled="taxonomyLoading || !taxonomy"
        @change="updatePrimaryLabel"
      ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部一级标签' : '分类配置暂不可用' }}</option><option
        v-for="item in taxonomy?.labels ?? []"
        :key="item.primary_label"
        :value="item.primary_label"
      >{{ item.primary_label }}</option></select></label>
      <label class="field field--label"><span>二级标签</span><select
        aria-label="二级标签"
        :value="secondaryLabel"
        :disabled="taxonomyLoading || !taxonomy || !primaryLabel"
        @change="emit('update:secondaryLabel', value($event))"
      ><option value="">{{ primaryLabel ? '全部二级标签' : '请先选择一级标签' }}</option><option
        v-for="item in secondaryLabels"
        :key="item"
        :value="item"
      >{{ item }}</option></select></label>
    </div>
    <footer class="filter-footer">
      <div class="filter-summary">
        <span>当前条件：</span><span class="filter-chip filter-chip--primary">{{ platform ? platformLabel(platform) : '全部平台' }}</span><span class="filter-chip">{{ voiceType || '全部发声类型' }}</span><span class="filter-chip">{{ vehicleModelIds.length ? `已选 ${vehicleModelIds.length} 款车型` : '全部车型' }}</span><span class="filter-chip">{{ primaryLabel || '全部一级标签' }}</span><button
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
.filters { min-width: 0; padding: 20px; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); }
.filter-row { display: grid; min-width: 0; align-items: start; gap: 16px; }
.filter-row--primary { grid-template-columns: minmax(240px, 1fr) 140px 150px 120px 130px 200px; }
.filter-row--secondary { grid-template-columns: 180px 160px 130px minmax(180px, 1fr) minmax(180px, 1fr); }
.field { display: grid; min-width: 0; gap: 6px; color: var(--aima-text-muted); font-size: 12px; font-weight: 700; }
.field input, .field select { width: 100%; height: 40px; min-width: 0; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; color: var(--aima-text-muted); background: var(--aima-surface); font: inherit; font-size: 13px; font-weight: 400; }
.field input::placeholder { color: var(--aima-text-disabled); }
.field select:disabled { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); cursor: not-allowed; }
.field input:focus-visible, .field select:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 1px; }
.filter-hint { margin: 10px 0 12px; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
.filter-footer { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; }
.filter-summary { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--aima-text-muted); font-size: 12px; }
.filter-chip { max-width: 100%; padding: 3px 8px; border: 0; border-radius: 4px; color: var(--aima-text-muted); background: var(--aima-color-bg-hover); font: inherit; overflow-wrap: anywhere; }
.filter-chip--primary { color: var(--aima-primary); background: var(--aima-primary-soft); }
.filter-actions { display: flex; flex: none; gap: 12px; }
@media (max-width: 1439px) {
  .filter-row--primary { grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(120px, 1fr)); }
  .field--status { grid-column: 1; }
  .field--date { grid-column: 2 / span 2; }
  .filter-row--secondary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .field--label { grid-column: auto; }
}
@media (max-width: 900px) {
  .filter-row--primary, .filter-row--secondary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .field--search, .field--date { grid-column: 1 / -1; }
  .field--status { grid-column: auto; }
  .filter-footer { align-items: flex-start; flex-wrap: wrap; }
}
</style>
