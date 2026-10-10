<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter, type LocationQueryRaw } from 'vue-router'

import AppShell from '../../../app/layouts/AppShell.vue'
import { useContentRevisionStore } from '../../../shared/api/contentRevision'
import type { WorkbenchLayoutModule, WorkbenchModuleId } from '../../../generated/api/client'
import { formatDateTime } from '../../../shared/domain/beijingTime'
import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'
import { useTaskCenterStore } from '../../task-center'
import BrandMindCard from '../components/BrandMindCard.vue'
import SoundStreamCard from '../components/SoundStreamCard.vue'
import UgcTrendCard from '../components/UgcTrendCard.vue'
import { useWorkbenchStore, type WorkbenchFilters } from '../store'
import { useIdentityStore } from '../../identity/store'

const store = useWorkbenchStore()
const identity = useIdentityStore()
const taskCenter = useTaskCenterStore()
const contentRevision = useContentRevisionStore()
let contentRevisionHandle: ReturnType<typeof setInterval> | undefined
const router = useRouter()
const draggedModule = ref<WorkbenchModuleId | null>(null)
let filterRefreshHandle: ReturnType<typeof setTimeout> | undefined
let analysisRefreshHandle: ReturnType<typeof setTimeout> | undefined
let periodicRefreshHandle: ReturnType<typeof setTimeout> | undefined
let periodicRefreshPending = false
const AUTO_REFRESH_INTERVAL = 60 * 60 * 1000
let pendingRefreshHandle: ReturnType<typeof setTimeout> | undefined
let pendingRefreshRunning = false
let pendingAttempts = 0
let pendingQuery = ''
let disposed = false
let resizeCleanup: (() => void) | null = null

const analysisFingerprint = computed(() =>
  (identity.isAdministrator ? taskCenter.analysisRuns : [])
    .map((run) => [
      run.id,
      run.status,
      run.stats?.succeeded ?? 0,
      run.stats?.failed ?? 0,
      run.stats?.stale ?? 0,
      run.stats?.cancelled ?? 0,
    ].join(':'))
    .join('|'),
)

/** 布局 Contract 的 row_units 决定卡片实际高度，固定视窗让内部列表独立滚动。 */
function moduleStyle(module: WorkbenchLayoutModule): Record<string, string> {
  return {
    gridColumn: `span ${module.column_span}`,
    height: `${Math.max(382, module.row_units * 8)}px`,
  }
}

/** 工作台数据更新时间按北京时间显示，值来自后端模块 as_of。 */
function refreshLabel(): string {
  return store.latestAsOf ? `${formatDateTime(store.latestAsOf)} · 每 1 小时检查更新` : '等待首次同步'
}

/** 连续多选操作短暂合并，日期确认则在当前事件中直接刷新。 */
function scheduleFilterRefresh(): void {
  if (filterRefreshHandle) clearTimeout(filterRefreshHandle)
  filterRefreshHandle = setTimeout(() => {
    filterRefreshHandle = undefined
    void store.refreshData()
  }, 100)
}

/** 内容修订号和管理员运行状态可能连续变化，750ms 内合并为一次刷新。 */
function scheduleAnalysisRefresh(): void {
  if (analysisRefreshHandle) clearTimeout(analysisRefreshHandle)
  analysisRefreshHandle = setTimeout(() => {
    analysisRefreshHandle = undefined
    void store.refreshData(true)
  }, 750)
}

/** 写入新的筛选草稿并按 debounce 触发三个模块的同口径刷新。 */
function updateFilters(value: WorkbenchFilters): void {
  store.setFilters(value)
  scheduleFilterRefresh()
}

/** 按上次请求完成时间安排下一轮，避免固定轮询与请求耗时错位而跳过整小时。 */
function schedulePeriodicRefresh(): void {
  if (periodicRefreshHandle) clearTimeout(periodicRefreshHandle)
  periodicRefreshHandle = undefined
  if (disposed || periodicRefreshPending || document.visibilityState !== 'visible') return
  const nextRefreshAt = (store.lastAutoRefreshAt ?? Date.now()) + AUTO_REFRESH_INTERVAL
  // 到期时其他模块仍在请求则短暂等待，不叠加请求或形成零延迟循环。
  periodicRefreshHandle = setTimeout(() => {
    periodicRefreshHandle = undefined
    void refreshPeriodically()
  }, Math.max(1000, nextRefreshAt - Date.now()))
}

/** 普通聚合刷新每一小时执行；慢请求与隐藏标签页不叠加。 */
async function refreshPeriodically(): Promise<void> {
  if (disposed || periodicRefreshPending) return
  if (document.visibilityState !== 'visible'
    || store.moduleLoading.stream || store.moduleLoading.mind || store.moduleLoading.trend
    || (store.lastAutoRefreshAt !== null && Date.now() - store.lastAutoRefreshAt < AUTO_REFRESH_INTERVAL)) {
    schedulePeriodicRefresh()
    return
  }
  periodicRefreshPending = true
  try {
    await store.refreshAggregates()
  } finally {
    periodicRefreshPending = false
    schedulePeriodicRefresh()
  }
}

/** 标签页恢复后只补充已经过期的普通刷新，并继续跟进后台计算。 */
function onVisibilityChange(): void {
  if (document.visibilityState === 'visible') {
    void contentRevision.refresh()
    void refreshPeriodically()
    schedulePendingRefresh()
  } else {
    schedulePeriodicRefresh()
  }
}

/** preparing/refreshing 是一次持久计算的完成跟进，与一小时普通刷新独立。 */
function schedulePendingRefresh(): void {
  if (pendingRefreshHandle) clearTimeout(pendingRefreshHandle)
  pendingRefreshHandle = undefined
  const query = JSON.stringify(store.filters)
  if (query !== pendingQuery) { pendingQuery = query; pendingAttempts = 0 }
  if (disposed || pendingRefreshRunning || pendingAttempts >= 120) return
  const pending = (status?: string) => status === 'preparing' || status === 'refreshing'
  if (!pending(store.mind?.snapshot_status) && !pending(store.trend?.snapshot_status)) return
  pendingRefreshHandle = setTimeout(async () => {
    pendingRefreshHandle = undefined
    if (disposed || document.visibilityState !== 'visible') { schedulePendingRefresh(); return }
    pendingRefreshRunning = true
    pendingAttempts += 1
    try {
      await Promise.all([
        pending(store.mind?.snapshot_status) ? store.refreshModule('mind', true) : Promise.resolve(),
        pending(store.trend?.snapshot_status) ? store.refreshModule('trend', true) : Promise.resolve(),
      ])
    } finally {
      pendingRefreshRunning = false
      schedulePendingRefresh()
    }
  }, Math.min(15_000, 3_000 * 2 ** Math.min(3, Math.floor(pendingAttempts / 5))))
}

/** 日期是一次确认动作，立即向后端请求三个模块。 */
function updateDateFilters(value: WorkbenchFilters): void {
  store.setFilters(value)
  if (filterRefreshHandle) clearTimeout(filterRefreshHandle)
  filterRefreshHandle = undefined
  void store.refreshData()
}

/** 重置为爱玛与截至昨日的完整七天，立即刷新。 */
function resetFilters(): void {
  store.resetFilters()
  if (filterRefreshHandle) clearTimeout(filterRefreshHandle)
  void store.refreshData()
}

/** 开始原生 Drag 时只记录模块身份，持久化仍等用户点击保存。 */
function dragStart(moduleId: WorkbenchModuleId): void {
  if (!store.editing) return
  draggedModule.value = moduleId
}

/** Drop 到另一模块时更新草稿 order，并清掉临时拖拽身份。 */
function dropOn(targetId: WorkbenchModuleId): void {
  if (draggedModule.value) store.reorderModule(draggedModule.value, targetId)
  draggedModule.value = null
}

/** 深链接完整携带已应用筛选；声音广场恢复时覆盖旧 Session。 */
function voicePlazaQuery(
  extra: { primaryLabel?: string; day?: string; contentId?: string } = {},
): LocationQueryRaw {
  const filters = store.filters
  const query: LocationQueryRaw = {
    published_from: extra.day ?? filters.dateFrom,
    published_to: extra.day ?? filters.dateTo,
  }
  if (filters.platforms.length) query.platforms = [...filters.platforms]
  if (filters.sentiments.length) query.sentiments = [...filters.sentiments]
  if (filters.voiceTypes.length) query.voice_types = [...filters.voiceTypes]
  if (extra.primaryLabel) {
    query.primary_labels = [extra.primaryLabel]
  } else {
    if (filters.primaryLabels.length) query.primary_labels = [...filters.primaryLabels]
  }
  if (filters.secondaryLabels.length) query.secondary_labels = [...filters.secondaryLabels]
  if (filters.brandIds.length) query.brand_ids = [...filters.brandIds]
  if (filters.vehicleModelIds.length) query.vehicle_model_ids = [...filters.vehicleModelIds]
  if (extra.contentId) query.content_id = extra.contentId
  return query
}

/** 打开声音广场并携带当前可表达筛选，形成 Workbench → 原声闭环。 */
async function openVoicePlaza(extra: { primaryLabel?: string; day?: string; contentId?: string } = {}): Promise<void> {
  await router.push({ path: '/voice-plaza', query: voicePlazaQuery(extra) })
}

/** Pointer Resize 只改当前模块草稿；宽高分别按 Contract 的单列/单行量化。 */
function startResize(event: PointerEvent, module: WorkbenchLayoutModule): void {
  if (!store.editing) return
  event.preventDefault()
  event.stopPropagation()
  resizeCleanup?.()
  const startX = event.clientX
  const startY = event.clientY
  const initialSpan = module.column_span
  const initialRows = module.row_units
  const grid = (event.currentTarget as HTMLElement | null)?.closest<HTMLElement>('.workbench-grid')
  const columnGap = grid ? Number.parseFloat(getComputedStyle(grid).columnGap) || 0 : 0
  const columnStep = grid
    ? (grid.clientWidth - columnGap * 11) / 12 + columnGap
    : 80

  /** Pointer 移动期间实时更新草稿几何，后端不会收到中间状态。 */
  const move = (moveEvent: PointerEvent): void => {
    const span = initialSpan + (moveEvent.clientX - startX) / columnStep
    const rows = initialRows + (moveEvent.clientY - startY) / 8
    store.resizeModule(module.module_id, span, rows)
  }

  /** Pointer 结束后移除全局监听，防止离开编辑态后仍修改草稿。 */
  const stop = (): void => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    resizeCleanup = null
  }

  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
  resizeCleanup = stop
}

/** 模块 id 转为编辑态中用户可理解的标题。 */
function moduleLabel(moduleId: WorkbenchModuleId): string {
  if (moduleId === 'sound-stream') return '声音流'
  if (moduleId === 'brand-mind') return '品牌用户心智'
  return 'UGC 声量与情感趋势'
}

watch(analysisFingerprint, (current, previous) => {
  if (identity.isAdministrator && previous && current !== previous) scheduleAnalysisRefresh()
})
watch(() => contentRevision.revision, (current, previous) => {
  if (previous !== null && current !== null && current !== previous) scheduleAnalysisRefresh()
})
watch([() => store.mind, () => store.trend, () => store.filters], schedulePendingRefresh)

onMounted(() => {
  void store.initialize().finally(schedulePeriodicRefresh)
  void contentRevision.refresh()
  contentRevisionHandle = setInterval(() => {
    if (document.visibilityState === 'visible') void contentRevision.refresh()
  }, 1000)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  disposed = true
  if (pendingRefreshHandle) clearTimeout(pendingRefreshHandle)
  if (filterRefreshHandle) clearTimeout(filterRefreshHandle)
  if (analysisRefreshHandle) clearTimeout(analysisRefreshHandle)
  if (periodicRefreshHandle) clearTimeout(periodicRefreshHandle)
  if (contentRevisionHandle) clearInterval(contentRevisionHandle)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  resizeCleanup?.()
})
</script>

<template>
  <AppShell section-title="工作台">
    <main class="workbench-page">
      <header class="workbench-header">
        <div>
          <h1>工作台</h1>
          <p>聚合全网小红书、抖音、微博等舆情洞察，通过 AI 引擎实时关注及分析</p>
        </div>
        <div class="header-actions">
          <span class="refresh-status">↻ {{ refreshLabel() }}</span>
          <template v-if="store.editing">
            <AimaButton
              size="small"
              :disabled="store.savingLayout"
              @click="store.cancelEditing()"
            >
              取消
            </AimaButton>
            <AimaButton
              size="small"
              variant="primary"
              :disabled="store.savingLayout"
              @click="store.saveLayout()"
            >
              {{ store.savingLayout ? '保存中…' : '保存完成' }}
            </AimaButton>
          </template>
          <AimaButton
            v-else
            size="small"
            variant="primary"
            :disabled="!store.layout"
            @click="store.startEditing()"
          >
            + 编辑工作台
          </AimaButton>
        </div>
      </header>

      <aside
        class="page-notices"
        aria-label="工作台状态"
      >
        <AimaFeedbackBanner
          v-if="store.globalError"
          tone="warning"
          role="status"
        >
          {{ store.globalError }}
        </AimaFeedbackBanner>
        <AimaFeedbackBanner
          v-if="store.referenceError"
          tone="warning"
        >
          {{ store.referenceError }}
        </AimaFeedbackBanner>
        <AimaFeedbackBanner
          v-if="store.layoutError"
          tone="error"
          role="alert"
        >
          <strong>布局尚未保存</strong>
          <span>{{ store.layoutError }}</span>
        </AimaFeedbackBanner>
        <AimaFeedbackBanner
          v-if="store.notice"
          tone="success"
        >
          {{ store.notice }}
        </AimaFeedbackBanner>
      </aside>

      <section
        v-if="store.editing"
        class="edit-toolbar"
        aria-label="工作台编辑提示"
      >
        <div>
          <strong>正在编辑工作台</strong>
          <span>拖动模块调整顺序，拖动右下角调整尺寸；所有变化先保存在本地草稿。</span>
        </div>
        <div
          v-if="store.hiddenModules.length"
          class="hidden-modules"
        >
          <span>已隐藏：</span>
          <button
            v-for="module in store.hiddenModules"
            :key="module.module_id"
            type="button"
            @click="store.setModuleVisible(module.module_id, true)"
          >
            + {{ moduleLabel(module.module_id) }}
          </button>
        </div>
      </section>

      <section
        class="workbench-grid"
        :class="{ 'workbench-grid--editing': store.editing }"
      >
        <div
          v-for="module in store.visibleModules"
          :key="module.module_id"
          class="module-shell"
          :class="{ 'module-shell--editing': store.editing }"
          :style="moduleStyle(module)"
          @dragover.prevent
          @drop.prevent="dropOn(module.module_id)"
        >
          <div
            v-if="store.editing"
            class="module-edit-controls"
          >
            <span
              class="drag-handle"
              title="拖动调整顺序"
              draggable="true"
              @dragstart.stop="dragStart(module.module_id)"
              @dragend.stop="draggedModule = null"
            >⠿</span>
            <button
              v-if="module.module_id !== 'sound-stream'"
              type="button"
              @click="store.setModuleVisible(module.module_id, false)"
            >
              隐藏
            </button>
          </div>

          <SoundStreamCard
            v-if="module.module_id === 'sound-stream'"
            :stream="store.stream"
            :filters="store.filters"
            :taxonomy="store.taxonomy"
            :brands="store.brands"
            :vehicle-models="store.vehicleModels"
            :loading="store.moduleLoading.stream"
            :error="store.moduleErrors.stream"
            @update:filters="updateFilters"
            @update:date-filters="updateDateFilters"
            @reset="resetFilters"
            @retry="store.refreshModule('stream')"
            @advance="store.advanceStream()"
            @open-all="openVoicePlaza()"
            @open-content="openVoicePlaza({ contentId: $event })"
          />
          <BrandMindCard
            v-else-if="module.module_id === 'brand-mind'"
            :mind="store.mind"
            :date-from="store.filters.dateFrom"
            :date-to="store.filters.dateTo"
            :brand-label="store.brandLabel"
            :selected-label="store.selectedMind"
            :metric="store.mindMetric"
            :loading="store.moduleLoading.mind"
            :error="store.moduleErrors.mind"
            @select="store.selectMind"
            @metric="store.setMindMetric"
            @retry="store.refreshModule('mind')"
            @open-voice="openVoicePlaza({ primaryLabel: $event })"
          />
          <UgcTrendCard
            v-else
            :trend="store.trend"
            :date-from="store.filters.dateFrom"
            :date-to="store.filters.dateTo"
            :loading="store.moduleLoading.trend"
            :error="store.moduleErrors.trend"
            @retry="store.refreshModule('trend')"
            @open-day="openVoicePlaza({ day: $event })"
          />

          <button
            v-if="store.editing"
            class="resize-handle"
            type="button"
            aria-label="调整模块尺寸"
            title="拖动调整模块尺寸"
            :draggable="false"
            @dragstart.stop.prevent
            @pointerdown="startResize($event, module)"
          >
            ◢
          </button>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<style scoped>
.workbench-page { position: relative; display: grid; gap: 8px; }
.page-notices { position: absolute; z-index: 40; top: 88px; right: 0; display: grid; gap: 4px; max-width: min(540px, 100%); }
.workbench-header { display: flex; min-height: 80px; align-items: center; justify-content: space-between; gap: 24px; padding: 12px 0; }
.workbench-header h1, .workbench-header p { margin: 0; }
.workbench-header h1 { color: var(--aima-text); font-size: var(--aima-font-size-page-title); line-height: 32px; }
.workbench-header p { margin-top: 6px; color: var(--aima-text-secondary); font-size: 12px; line-height: 18px; }
.header-actions { display: flex; flex: none; align-items: center; gap: 8px; }
.refresh-status { margin-right: 8px; color: #e03d6f; font-size: 12px; font-weight: 600; white-space: nowrap; }
.edit-toolbar { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 12px; border: 1px solid var(--aima-primary-soft-strong); border-radius: 8px; background: var(--aima-primary-soft); }
.edit-toolbar > div:first-child { display: grid; gap: 2px; }
.edit-toolbar strong { color: var(--aima-text); font-size: 12px; }
.edit-toolbar span { color: var(--aima-text-secondary); font-size: 10px; }
.hidden-modules { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }
.hidden-modules button { padding: 3px 7px; border: 1px solid var(--aima-border-strong); border-radius: 5px; color: var(--aima-primary); background: #fff; cursor: pointer; font-size: 10px; }
.workbench-grid { display: grid; min-width: 0; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 20px; padding-bottom: 20px; align-items: stretch; }
.module-shell { position: relative; min-width: 0; box-sizing: border-box; container-type: size; }
.module-shell--editing { padding: 5px; border: 1px dashed var(--aima-primary); border-radius: 10px; background: rgb(255 238 246 / 35%); }
.module-edit-controls { position: absolute; z-index: 30; top: 10px; right: 10px; display: flex; align-items: center; gap: 5px; padding: 3px 5px; border: 1px solid var(--aima-border); border-radius: 6px; background: rgb(255 255 255 / 94%); box-shadow: 0 2px 8px rgb(23 35 61 / 10%); }
.drag-handle { color: var(--aima-primary); cursor: grab; font-size: 14px; line-height: 18px; }
.module-edit-controls button { border: 0; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 10px; }
.resize-handle { position: absolute; z-index: 31; right: 8px; bottom: 8px; display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid var(--aima-primary); border-radius: 5px; color: var(--aima-primary); background: #fff; cursor: nwse-resize; touch-action: none; }
@media (max-width: 1180px) {
  .workbench-header { align-items: flex-start; flex-wrap: wrap; }
  .header-actions { width: 100%; justify-content: flex-end; }
  .workbench-grid { grid-template-columns: minmax(0, 1fr); }
  .module-shell { grid-column: 1 / -1 !important; }
  .edit-toolbar { align-items: flex-start; flex-direction: column; }
}
</style>
