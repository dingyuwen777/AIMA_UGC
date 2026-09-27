<script setup lang="ts">
import { computed } from 'vue'

import type {
  BrandResponse,
  ContentAnalysisTaxonomyResponse,
  VehicleModelResponse,
  WorkbenchStreamResponse,
} from '../../../generated/api/client'
import { platformLabel } from '../../../shared/domain/platform'
import type { WorkbenchFilters } from '../store'
import WorkbenchFiltersBar from './WorkbenchFilters.vue'

const props = defineProps<{
  stream: WorkbenchStreamResponse | null
  filters: WorkbenchFilters
  taxonomy: ContentAnalysisTaxonomyResponse | null
  brands: BrandResponse[]
  vehicleModels: VehicleModelResponse[]
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  'update:filters': [value: WorkbenchFilters]
  reset: []
  retry: []
  openAll: []
}>()

const items = computed(() => props.stream?.items.slice(0, 6) ?? [])

/** 用北京时间展示声音列表的紧凑月日，不受浏览器本地时区影响。 */
function compactDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
}

/** 优先展示正文，再回退标题；没有文本时给出明确空值而不是空白行。 */
function contentText(item: WorkbenchStreamResponse['items'][number]): string {
  return item.text?.trim() || item.title?.trim() || '暂无正文摘要'
}
</script>

<template>
  <section class="workbench-card stream-card">
    <header class="card-header">
      <div class="card-title">
        <span class="card-icon">♫</span>
        <div>
          <h2>声音流</h2>
          <p>聚合全渠道舆情、UGC 反馈和采集得到的真实用户原声流</p>
        </div>
      </div>
    </header>

    <WorkbenchFiltersBar
      :model-value="filters"
      :taxonomy="taxonomy"
      :brands="brands"
      :vehicle-models="vehicleModels"
      :loading="loading"
      @update:model-value="emit('update:filters', $event)"
      @reset="emit('reset')"
    />

    <div
      v-if="error"
      class="module-state module-state--error"
      role="alert"
    >
      <strong>声音流暂时无法更新</strong>
      <span>继续保留上次成功结果。</span>
      <button
        type="button"
        @click="emit('retry')"
      >
        重试
      </button>
    </div>

    <div
      v-if="loading && items.length === 0"
      class="module-state"
    >
      正在加载声音流…
    </div>
    <div
      v-else-if="items.length === 0 && !error"
      class="module-state"
    >
      当前筛选范围暂无声音记录
    </div>
    <div
      v-else
      class="stream-list"
    >
      <article
        v-for="item in items"
        :key="item.content_id"
      >
        <span class="platform-badge">{{ platformLabel(item.platform).slice(0, 1) }}</span>
        <div class="stream-main">
          <div class="stream-meta">
            <strong>{{ item.author_display_name || '匿名用户' }}</strong>
            <time>{{ compactDate(item.published_at) }}</time>
            <span>{{ platformLabel(item.platform) }}</span>
          </div>
          <p>{{ contentText(item) }}</p>
        </div>
        <div class="stream-tags">
          <span v-if="item.sentiment">{{ item.sentiment }}</span>
          <span v-if="item.vehicle_names?.[0]">{{ item.vehicle_names[0] }}</span>
          <span v-if="item.labels?.[0]">{{ item.labels[0].primary_label }}</span>
          <em v-if="!item.analysis_current">待当前规则分析</em>
        </div>
      </article>
    </div>

    <footer>
      <span>
        已展示最新 {{ items.length }} 条声音
        <template v-if="stream?.as_of"> · 数据已同步</template>
      </span>
      <button
        type="button"
        @click="emit('openAll')"
      >
        查看全部声音 →
      </button>
    </footer>
  </section>
</template>

<style scoped>
.workbench-card {
  display: flex;
  height: 100%;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: var(--aima-surface);
  box-shadow: 0 4px 12px -2px rgb(23 35 61 / 4%), 0 1px 6px rgb(23 35 61 / 8%);
}
.card-header { min-height: 44px; border-bottom: 1px solid var(--aima-border); }
.card-title { display: flex; align-items: center; gap: 8px; }
.card-title h2, .card-title p { margin: 0; }
.card-title h2 { color: var(--aima-text); font-size: 16px; line-height: 22px; }
.card-title p { margin-top: 2px; color: var(--aima-text-secondary); font-size: 11px; line-height: 16px; }
.card-icon { display: inline-grid; width: 28px; height: 28px; place-items: center; border-radius: 50%; color: var(--aima-primary); background: var(--aima-primary-soft); }
.stream-list { display: grid; min-height: 0; flex: 1; gap: 6px; overflow: auto; }
.stream-list article { display: grid; min-height: 44px; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 6px 8px; border: 1px solid var(--aima-border); border-radius: 6px; }
.platform-badge { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; color: #fff; background: var(--aima-text-secondary); font-size: 10px; font-weight: 700; }
.stream-main { min-width: 0; }
.stream-meta { display: flex; gap: 7px; align-items: center; color: var(--aima-text-disabled); font-size: 10px; }
.stream-meta strong { color: var(--aima-text); font-size: 11px; }
.stream-main > p { margin: 3px 0 0; overflow: hidden; color: var(--aima-text); font-size: 11px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
.stream-tags { display: flex; max-width: 190px; flex-wrap: wrap; justify-content: flex-end; gap: 3px; }
.stream-tags span, .stream-tags em { padding: 2px 5px; border-radius: 3px; background: var(--aima-primary-soft); color: var(--aima-primary); font-size: 9px; font-style: normal; }
.stream-tags span:nth-child(2) { color: #d97706; background: #fff3e6; }
.stream-tags span:nth-child(3) { color: var(--aima-color-accent-purple); background: #f3e8ff; }
.stream-tags em { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); }
.module-state { display: grid; min-height: 120px; place-content: center; gap: 5px; color: var(--aima-text-disabled); text-align: center; font-size: 12px; }
.module-state--error { color: var(--aima-danger); }
.module-state--error span { color: var(--aima-text-secondary); }
.module-state button, footer button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
footer { display: flex; min-height: 20px; align-items: center; justify-content: space-between; color: var(--aima-text-disabled); font-size: 10px; }
</style>
