<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  BrandResponse,
  ContentAnalysisTaxonomyResponse,
  VehicleModelResponse,
  WorkbenchStreamResponse,
} from '../../../generated/api/client'
import { platformLabel } from '../../../shared/domain/platform'
import AimaPlatformMark from '../../../shared/ui/AimaPlatformMark.vue'
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
  'update:date-filters': [value: WorkbenchFilters]
  reset: []
  retry: []
  advance: []
  openAll: []
  openContent: [contentId: string]
}>()

const items = computed(() => props.stream?.items ?? [])
const scrollList = ref<HTMLElement | null>(null)
const firstCycle = ref<HTMLElement | null>(null)
const repeatCount = ref(2)
const hovered = ref(false)
const focused = ref(false)
let autoScrollHandle = 0
let resizeObserver: ResizeObserver | undefined
let reducedMotion: MediaQueryList | undefined
let lastFrameTime = 0
let advancingPage = false

/** Figma 的两段同内容轨道首尾相接；短列表增加副本以覆盖可见区域。 */
function resizeTrack(): void {
  const list = scrollList.value
  const cycle = firstCycle.value
  if (!list || !cycle || cycle.offsetHeight === 0) return
  repeatCount.value = Math.min(12, Math.max(2, Math.ceil(list.clientHeight / (cycle.offsetHeight + 6)) + 2))
}

/** 按真实经过时间匀速移动，越过第一段时无缝回到同一内容位置。 */
function advanceScroll(timestamp: number): void {
  autoScrollHandle = requestAnimationFrame(advanceScroll)
  const list = scrollList.value
  const cycle = firstCycle.value
  const elapsed = lastFrameTime ? Math.min(50, timestamp - lastFrameTime) : 0
  lastFrameTime = timestamp
  if (!list || !cycle || items.value.length < 2 || props.loading || props.error
    || hovered.value || focused.value || document.hidden || reducedMotion?.matches) return
  const cycleHeight = cycle.offsetHeight + 6
  if (!cycleHeight || list.scrollHeight <= list.clientHeight) return
  const nextTop = list.scrollTop + elapsed * 0.04
  if (nextTop >= cycleHeight) {
    list.scrollTop = nextTop % cycleHeight
    if (!advancingPage) {
      advancingPage = true
      emit('advance')
    }
  } else {
    list.scrollTop = nextTop
  }
}

onMounted(() => {
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
  resizeObserver = new ResizeObserver(resizeTrack)
  autoScrollHandle = requestAnimationFrame(advanceScroll)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(autoScrollHandle)
  resizeObserver?.disconnect()
})
watch([scrollList, firstCycle], async () => {
  await nextTick()
  resizeObserver?.disconnect()
  if (scrollList.value) resizeObserver?.observe(scrollList.value)
  if (firstCycle.value) resizeObserver?.observe(firstCycle.value)
  resizeTrack()
})
watch(() => props.stream, async (_current, previous) => {
  await nextTick()
  advancingPage = false
  if (scrollList.value && props.stream?.items[0]?.content_id !== previous?.items[0]?.content_id) scrollList.value.scrollTop = 0
  resizeTrack()
})
watch(() => props.loading, (loading) => {
  // 自动翻页请求无论成功或失败都允许下一轮继续推进；成功时 stream watch 还会
  // 把滚动位置复位到新页起点。
  if (!loading) advancingPage = false
})

/** 用北京时间展示真实发帖月日与时分，不受浏览器本地时区影响。 */
function compactDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(value))
}

/** 优先展示正文，再回退标题；没有文本时给出明确空值而不是空白行。 */
function contentText(item: WorkbenchStreamResponse['items'][number]): string {
  return item.text?.trim() || item.title?.trim() || '暂无正文摘要'
}
</script>

<template>
  <section
    class="workbench-card stream-card"
    :aria-busy="loading"
  >
    <header class="card-header">
      <div class="card-title">
        <span class="card-icon">♫</span>
        <div>
          <h2>声音流</h2>
          <p>聚合全渠道舆情、UGC 反馈和采集得到的真实用户原声流</p>
        </div>
      </div>
      <div
        class="card-refresh-state"
        role="status"
      >
        <template v-if="error && stream">
          <span>更新失败，保留上次结果</span><button
            type="button"
            @click="emit('retry')"
          >
            重试
          </button>
        </template>
        <span v-else-if="loading">更新中…</span>
      </div>
    </header>

    <WorkbenchFiltersBar
      :model-value="filters"
      :taxonomy="taxonomy"
      :brands="brands"
      :vehicle-models="vehicleModels"
      @update:model-value="emit('update:filters', $event)"
      @update:date="emit('update:date-filters', $event)"
      @reset="emit('reset')"
    />

    <div
      v-if="error && !stream"
      class="module-state module-state--error"
      :class="{ 'module-state--inline': items.length > 0 }"
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
      ref="scrollList"
      class="stream-list"
      role="region"
      aria-label="声音流列表"
      tabindex="0"
      @mouseenter="hovered = true"
      @mouseleave="hovered = false"
      @focusin="focused = true"
      @focusout="focused = false"
    >
      <div class="stream-track">
        <div
          v-for="copy in items.length > 1 ? repeatCount : 1"
          :key="copy"
          :ref="copy === 1 ? (element) => { firstCycle = element as HTMLElement | null } : undefined"
          class="stream-cycle"
          :aria-hidden="copy > 1 ? 'true' : undefined"
        >
          <article
            v-for="item in items"
            :key="item.content_id"
            :role="copy === 1 ? 'button' : undefined"
            :tabindex="copy === 1 ? 0 : -1"
            :aria-label="copy === 1 ? `在声音广场查看${contentText(item)}` : undefined"
            @click="copy === 1 && emit('openContent', item.content_id)"
            @keydown.enter="copy === 1 && emit('openContent', item.content_id)"
            @keydown.space.prevent="copy === 1 && emit('openContent', item.content_id)"
          >
            <AimaPlatformMark :platform="item.platform" />
            <div class="stream-main">
              <div class="stream-meta">
                <strong>{{ item.author_display_name || '未知作者' }}</strong>
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
      </div>
    </div>

    <footer>
      <span>
        正在遍历当前筛选范围 · 本页 {{ items.length }} 条
        <template v-if="stream?.has_more"> · 后续还有内容</template>
        <template v-if="stream?.as_of && !loading && !error"> · 数据已同步</template>
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
.card-header { position: relative; flex: none; }
.card-refresh-state { position: absolute; bottom: 1px; right: 12px; display: flex; gap: 5px; color: var(--aima-text-muted); font-size: 9px; line-height: 11px; }
.card-refresh-state button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font: inherit; }
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
.card-header { display: flex; min-height: 44px; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid var(--aima-border); }
.card-title { display: flex; min-width: 0; align-items: center; gap: 8px; }
.card-title > div { min-width: 0; }
.card-title h2, .card-title p { margin: 0; }
.card-title h2 { color: var(--aima-text); font-size: 16px; line-height: 22px; }
.card-title p { margin-top: 2px; overflow: hidden; color: var(--aima-text-secondary); font-size: 11px; line-height: 16px; text-overflow: ellipsis; white-space: nowrap; }
.card-icon { display: inline-grid; width: 28px; height: 28px; place-items: center; border-radius: 50%; color: var(--aima-primary); background: var(--aima-primary-soft); }
.stream-list { min-height: 0; flex: 1; overflow: auto; overscroll-behavior: contain; scrollbar-width: none; }
.stream-list::-webkit-scrollbar { display: none; }
.stream-track, .stream-cycle { display: grid; align-content: start; gap: 6px; }
.refresh-note { margin: 0; color: var(--aima-text-secondary); font-size: 10px; }
.stream-list article { display: grid; min-height: 44px; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 6px 8px; border: 1px solid var(--aima-border); border-radius: 6px; cursor: pointer; }
.stream-list article:hover, .stream-list article:focus-visible { border-color: var(--aima-primary); background: var(--aima-primary-soft); outline: none; }
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
.module-state--inline { min-height: 0; grid-template-columns: auto auto auto; align-items: center; justify-content: start; margin: 0 12px; padding: 5px 8px; border-radius: 5px; background: var(--aima-primary-soft); text-align: left; font-size: 10px; }
.module-state button, footer button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
footer { display: flex; min-height: 20px; align-items: center; justify-content: space-between; color: var(--aima-text-disabled); font-size: 10px; }
@container (max-width: 520px) {
  .stream-list article { grid-template-columns: 24px minmax(0, 1fr); }
  .stream-tags { max-width: none; grid-column: 2; justify-content: flex-start; }
  footer { align-items: flex-start; flex-direction: column; gap: 4px; }
}
</style>
