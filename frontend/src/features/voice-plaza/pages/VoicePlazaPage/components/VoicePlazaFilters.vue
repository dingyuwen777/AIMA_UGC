<script setup lang="ts">
import { computed, ref } from 'vue'

import type {
  ContentAnalysisStatus,
  ContentAnalysisTaxonomyResponse,
  ContentRelevance,
  PlatformName,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
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

const advancedOpen = ref(false)
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
const advancedFilterCount = computed(() => [
  props.voiceType,
  props.sentiment,
  props.analysisStatus,
  props.contentType,
  props.primaryLabel,
  props.secondaryLabel,
].filter(Boolean).length)

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
        :value="platform"
        @change="emit('update:platform', value($event) as '' | PlatformName)"
      ><option value="">全部平台</option><option value="xiaohongshu">小红书</option><option value="douyin">抖音</option><option value="weibo">微博</option><option value="bilibili">B站</option><option value="kuaishou">快手</option></select></label>
      <label class="field field--relevance"><span>相关性</span><select
        :value="relevance"
        @change="emit('update:relevance', value($event) as '' | ContentRelevance)"
      ><option value="">默认业务数据</option><option value="relevant">相关</option><option value="irrelevant">不相关</option></select></label>
      <label class="field field--date"><span>发布开始</span><input
        type="date"
        :value="publishedFrom"
        aria-label="发布开始"
        @input="emit('update:publishedFrom', value($event))"
      ></label>
      <label class="field field--date"><span>发布结束</span><input
        type="date"
        :value="publishedTo"
        aria-label="发布结束"
        @input="emit('update:publishedTo', value($event))"
      ></label>
    </div>

    <VehicleMultiSelect
      :model-value="vehicleModelIds"
      label="车型"
      @update:model-value="emit('update:vehicleModelIds', $event)"
    />

    <div class="filter-toolbar">
      <button
        class="advanced-toggle"
        type="button"
        :aria-expanded="advancedOpen"
        @click="advancedOpen = !advancedOpen"
      >
        {{ advancedOpen ? '收起筛选' : '更多筛选' }}<span v-if="advancedFilterCount">（{{ advancedFilterCount }}）</span>
      </button>
      <span v-if="!advancedOpen && advancedFilterCount">已应用 {{ advancedFilterCount }} 个更多筛选条件</span>
    </div>

    <div
      v-show="advancedOpen"
      class="advanced-filters"
    >
      <div class="filter-row filter-row--secondary">
        <label class="field field--voice-type"><span>发声类型</span><select
          :value="voiceType"
          :disabled="taxonomyLoading || !taxonomy"
          @change="emit('update:voiceType', value($event))"
        ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部发声类型' : '分类配置暂不可用' }}</option><option
          v-for="item in taxonomy?.voice_types ?? []"
          :key="item"
          :value="item"
        >{{ item }}</option></select></label>
        <label class="field field--sentiment"><span>情感</span><select
          :value="sentiment"
          :disabled="taxonomyLoading || !taxonomy"
          @change="emit('update:sentiment', value($event))"
        ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部情感' : '分类配置暂不可用' }}</option><option
          v-for="item in taxonomy?.sentiments ?? []"
          :key="item"
          :value="item"
        >{{ item }}</option></select></label>
        <label class="field field--status"><span>分析状态</span><select
          :value="analysisStatus"
          @change="emit('update:analysisStatus', value($event) as '' | ContentAnalysisStatus)"
        ><option value="">全部状态</option><option value="completed">已分析</option><option value="pending">未分析</option><option value="stale">需重新分析</option></select></label>
        <label class="field field--content-type"><span>内容类型</span><select
          :value="contentType"
          @change="emit('update:contentType', value($event))"
        ><option value="">全部类型</option><option
          v-for="item in contentTypeOptions"
          :key="item.value"
          :value="item.value"
        >{{ item.label }}</option></select></label>
        <label class="field field--label"><span>一级标签</span><select
          :value="primaryLabel"
          :disabled="taxonomyLoading || !taxonomy"
          @change="updatePrimaryLabel"
        ><option value="">{{ taxonomyLoading ? '分类配置加载中' : taxonomy ? '全部一级标签' : '分类配置暂不可用' }}</option><option
          v-for="item in taxonomy?.labels ?? []"
          :key="item.primary_label"
          :value="item.primary_label"
        >{{ item.primary_label }}</option></select></label>
        <label class="field field--label"><span>二级标签</span><select
          :value="secondaryLabel"
          :disabled="taxonomyLoading || !taxonomy || !primaryLabel"
          @change="emit('update:secondaryLabel', value($event))"
        ><option value="">{{ primaryLabel ? '全部二级标签' : '请先选择一级标签' }}</option><option
          v-for="item in secondaryLabels"
          :key="item"
          :value="item"
        >{{ item }}</option></select></label>
      </div>
      <p class="advanced-note">
        标签和发声类型随当前生效的 AI 分析方案更新；车型来自管理员维护的车型目录。
      </p>
    </div>

    <footer class="filter-footer">
      <p>搜索、平台、车型、相关性和发布时间直接筛选；AI 状态、情感、发声类型、标签和内容类型收纳在“更多筛选”中。</p>
      <div class="filter-actions">
        <AimaButton
          size="small"
          @click="emit('reset')"
        >
          重置
        </AimaButton>
        <AimaButton
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
.filters {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--aima-border);
  border-radius: var(--aima-radius-control);
  background: var(--aima-surface);
}
.filter-row { display: flex; min-width: 0; align-items: flex-start; gap: 10px; }
.field { display: grid; min-width: 0; gap: 6px; color: var(--aima-text-muted); font-size: 11px; font-weight: 500; }
.field--search { flex: 0 1 280px; }
.field--platform { flex: 0 1 120px; }
.field--relevance { flex: 0 1 120px; }
.field--voice-type { flex: 0 1 150px; }
.field--sentiment { flex: 0 1 120px; }
.field--status { flex: 0 1 130px; }
.field--content-type { flex: 0 1 140px; }
.field--label { flex: 0 1 200px; }
.field--date { flex: 0 1 190px; }
input,
select {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--aima-border-strong);
  border-radius: var(--aima-radius-control);
  outline: none;
  color: var(--aima-text-secondary);
  background: var(--aima-surface);
  font: inherit;
  font-size: 13px;
  font-weight: 400;
  line-height: 20px;
}
input::placeholder { color: var(--aima-text-disabled); }
select:disabled { cursor: not-allowed; color: var(--aima-text-disabled); background: #f5f7fa; }
input:focus,
select:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-primary-soft); }
.filter-toolbar { display: flex; min-height: 28px; align-items: center; gap: 10px; color: var(--aima-text-disabled); font-size: 11px; }
.advanced-toggle {
  padding: 0;
  border: 0;
  color: var(--aima-primary);
  background: transparent;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.advanced-toggle:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 3px; }
.advanced-filters { display: grid; gap: 12px; padding-top: 2px; }
.advanced-note { margin: 0; color: var(--aima-text-disabled); font-size: 11px; line-height: 16px; }
.filter-footer { display: flex; min-height: 36px; align-items: center; justify-content: space-between; gap: 16px; border-top: 1px solid var(--aima-border); padding-top: 10px; }
.filter-footer p { margin: 0; color: var(--aima-text-disabled); font-size: 11px; font-weight: 400; line-height: 16px; }
.filter-actions { display: flex; flex: none; align-items: center; gap: 8px; }
.filter-actions :deep(.aima-button) { height: 36px; padding-inline: 16px; font-size: 13px; }
@media (max-width: 1280px) {
  .filter-row { flex-wrap: wrap; }
  .field--search { flex-basis: 300px; }
  .field:not(.field--search) { flex: 1 1 150px; }
}
</style>
