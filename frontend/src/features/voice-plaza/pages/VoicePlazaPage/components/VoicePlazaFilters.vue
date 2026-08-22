<script setup lang="ts">
import type { ContentAnalysisStatus } from '../../../../../generated/api/client'

defineProps<{
  search: string
  platform: string
  contentType: string
  analysisStatus: '' | ContentAnalysisStatus
  sentiment: string
  primaryLabel: string
  secondaryLabel: string
  publishedFrom: string
  publishedTo: string
  sourceIdentifier: string
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:platform': [value: string]
  'update:contentType': [value: string]
  'update:analysisStatus': [value: '' | ContentAnalysisStatus]
  'update:sentiment': [value: string]
  'update:primaryLabel': [value: string]
  'update:secondaryLabel': [value: string]
  'update:publishedFrom': [value: string]
  'update:publishedTo': [value: string]
  'update:sourceIdentifier': [value: string]
  search: []
  reset: []
}>()

function value(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value
}
</script>

<template>
  <section
    class="filters"
    aria-label="声音广场筛选条件"
  >
    <label class="search-field wide"><span>搜索内容</span><input
      :value="search"
      placeholder="搜索标题、正文、作者或外部内容 ID"
      @input="emit('update:search', value($event))"
      @keyup.enter="emit('search')"
    ></label>
    <label><span>平台</span><select
      :value="platform"
      @change="emit('update:platform', value($event))"
    ><option value="">全部平台</option><option value="xiaohongshu">小红书</option><option value="douyin">抖音</option><option value="weibo">微博</option><option value="bilibili">B站</option><option value="kuaishou">快手</option><option value="file">Excel 导入</option></select></label>
    <label><span>AI 情感</span><select
      :value="sentiment"
      @change="emit('update:sentiment', value($event))"
    ><option value="">全部情感</option><option value="正面">正面</option><option value="中性">中性</option><option value="负面">负面</option></select></label>
    <label><span>AI 状态</span><select
      :value="analysisStatus"
      @change="emit('update:analysisStatus', value($event) as '' | ContentAnalysisStatus)"
    ><option value="">全部状态</option><option value="completed">已打标</option><option value="pending">未打标</option><option value="stale">需重新打标</option></select></label>
    <label><span>内容类型</span><input
      :value="contentType"
      placeholder="如 note、video"
      @input="emit('update:contentType', value($event))"
    ></label>
    <label><span>一级标签</span><input
      :value="primaryLabel"
      placeholder="精确匹配"
      @input="emit('update:primaryLabel', value($event))"
    ></label>
    <label><span>二级标签</span><input
      :value="secondaryLabel"
      placeholder="精确匹配"
      @input="emit('update:secondaryLabel', value($event))"
    ></label>
    <label><span>来源 Batch / Run ID</span><input
      :value="sourceIdentifier"
      placeholder="UUID"
      @input="emit('update:sourceIdentifier', value($event))"
    ></label>
    <label><span>发布开始</span><input
      type="date"
      :value="publishedFrom"
      @input="emit('update:publishedFrom', value($event))"
    ></label>
    <label><span>发布结束</span><input
      type="date"
      :value="publishedTo"
      @input="emit('update:publishedTo', value($event))"
    ></label>
    <div class="filter-actions">
      <button
        type="button"
        @click="emit('reset')"
      >
        条件重置
      </button><button
        class="primary"
        type="button"
        @click="emit('search')"
      >
        查询
      </button>
    </div>
  </section>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: 2fr repeat(4, minmax(140px, 1fr)); gap: 14px 12px; margin-top: 18px; padding: 18px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; }
label { display: flex; min-width: 0; flex-direction: column; gap: 7px; color: #5f6879; font-size: 12px; }
label.wide { grid-column: span 2; }
input, select { width: 100%; height: 38px; padding: 0 11px; border: 1px solid #dfe3ea; border-radius: 6px; outline: none; color: #343d4f; background: #fff; }
input:focus, select:focus { border-color: var(--aima-primary); box-shadow: 0 0 0 2px rgb(245 0 87 / 8%); }
.filter-actions { display: flex; align-items: flex-end; justify-content: flex-end; gap: 10px; }
button { height: 38px; padding: 0 18px; border: 1px solid #d9dee7; border-radius: 6px; color: #535d6f; background: #fff; cursor: pointer; }
button.primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
@media (max-width: 1450px) { .filters { grid-template-columns: 2fr repeat(3, minmax(135px, 1fr)); } }
</style>
