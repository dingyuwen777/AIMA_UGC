<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '../../../../app/layouts/AppShell.vue'
import type {
  AnalysisContentRunResponse,
  ContentRelevanceReviewResponse,
  DataExportResponse,
  ExportColumnKey,
} from '../../../../generated/api/client'
import TaskProgressBar from '../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../../shared/ui/AimaPageHeader.vue'
import { useTaskCenterStore } from '../../../task-center'
import {
  relevanceReviewDecision,
  type RelevanceReviewDecision,
} from '../../relevanceReview'
import { useVoicePlazaStore } from '../../store'
import AnalysisSubmitDialog from './components/AnalysisSubmitDialog.vue'
import ContentDetailDrawer from './components/ContentDetailDrawer.vue'
import DataExportDialog from './components/DataExportDialog.vue'
import VoicePlazaFilters from './components/VoicePlazaFilters.vue'
import VoicePlazaTable from './components/VoicePlazaTable.vue'

const store = useVoicePlazaStore()
const taskCenter = useTaskCenterStore()
const route = useRoute()
const analysisOpen = ref(false)
const exportOpen = ref(false)
const notice = ref<string | null>(null)
const activeAnalysisRuns = computed(() => store.analysisRuns.filter(
  (run) => run.status === 'queued' || run.status === 'running' || run.status === 'cancelling',
))
const selectedReviewIds = computed<Record<RelevanceReviewDecision, string[]>>(() => {
  const grouped: Record<RelevanceReviewDecision, string[]> = {
    relevant: [],
    irrelevant: [],
    inherit_ai: [],
  }
  const selected = new Set(store.selectedIds)
  for (const item of store.items) {
    if (!selected.has(item.id)) continue
    const decision = relevanceReviewDecision(item)
    if (decision) grouped[decision].push(item.id)
  }
  return grouped
})
const reviewNote = computed(() => {
  if (store.filters.relevance === 'irrelevant') {
    return '当前显示业务有效不相关内容：AI 原判不相关的内容可人工标记为相关；被人工排除的内容可撤销人工判断。AI 原始结果始终保留。'
  }
  if (store.filters.relevance === 'relevant') {
    return '当前显示业务有效相关内容：AI 原判相关的内容可人工标记为不相关；被人工纳入的内容可撤销人工判断。AI 原始结果始终保留。'
  }
  return null
})
const runStatusLabels: Record<AnalysisContentRunResponse['status'], string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  partial_failed: '部分失败',
  failed: '失败',
  cancelling: '取消中',
  cancelled: '已取消',
}
const detailOpen = computed({
  get: () => store.detail !== null || store.loadingDetail,
  set: (open: boolean) => { if (!open) store.closeDetail() },
})

onMounted(async () => {
  const sourceIdentifier = route.query.source_identifier
  if (typeof sourceIdentifier === 'string') store.filters.sourceIdentifier = sourceIdentifier
  await refreshPage()
  store.startPolling(5000)
})
onBeforeUnmount(() => store.stopPolling())

/** 先校准分类筛选，再并行刷新列表和独立业务资源。 */
async function refreshPage(): Promise<void> {
  await store.refreshTaxonomy()
  await Promise.all([
    store.refresh(),
    store.refreshExports(),
    store.refreshAnalysisCapabilities(),
    store.refreshAnalysisRuns(),
  ])
  void taskCenter.refresh(true)
}

/** 提交当前筛选并清空旧选择，避免跨查询误操作。 */
async function search(): Promise<void> {
  store.clearSelection()
  await store.refresh()
}

/** 恢复默认筛选并重新获取第一页。 */
async function reset(): Promise<void> {
  store.resetFilters()
  await store.refresh()
}

/** 把人工相关性复核结果转换为用户可读反馈。 */
function relevanceNotice(
  decision: RelevanceReviewDecision,
  result: ContentRelevanceReviewResponse,
): string {
  const unchanged = result.unchanged_count > 0 ? `，${result.unchanged_count} 条无需变化` : ''
  if (decision === 'relevant') return `已人工标记 ${result.changed_count} 条内容为相关${unchanged}。`
  if (decision === 'irrelevant') return `已人工标记 ${result.changed_count} 条内容为不相关${unchanged}。`
  return `已撤销 ${result.changed_count} 条人工相关性判断${unchanged}。`
}

/** 对单条内容执行既有人工相关性复核流程。 */
async function reviewSingle(
  contentId: string,
  decision: RelevanceReviewDecision,
): Promise<void> {
  const result = await store.reviewRelevance([contentId], decision)
  if (result) showNotice(relevanceNotice(decision, result))
}

/** 对当前选择中具有相同复核决策的内容执行批量复核。 */
async function reviewSelected(decision: RelevanceReviewDecision): Promise<void> {
  const contentIds = selectedReviewIds.value[decision]
  const result = await store.reviewRelevance(contentIds, decision)
  if (result) showNotice(relevanceNotice(decision, result))
}

/** 使用预检冻结信息确认创建 Analysis Run，并同步全局任务中心。 */
async function submitAnalysis(): Promise<void> {
  const count = await store.confirmAnalysis()
  if (count === null) return
  analysisOpen.value = false
  showNotice(`已创建 AI Analysis Run，冻结 ${count} 条内容。`)
  void taskCenter.refresh(true)
}

/** 请求取消仍处于可取消状态的 Analysis Run，并同步全局任务中心。 */
async function cancelAnalysis(runId: string): Promise<void> {
  if (await store.cancelRun(runId)) {
    showNotice('已请求取消 Analysis Run。')
    void taskCenter.refresh(true)
  }
}

/** 创建 selected/page/query 三种既有范围之一的 Excel 导出。 */
async function submitExport(
  scope: 'query' | 'selected' | 'page',
  columns: ExportColumnKey[],
): Promise<void> {
  const count = await store.createExport(scope, columns)
  if (count === null) return
  showNotice(`已创建 Excel 导出 Job，冻结 ${count} 条内容。`)
  void taskCenter.refresh(true)
}

/** 下载已经就绪且仍在保留期内的导出 Artifact。 */
async function download(item: DataExportResponse): Promise<void> {
  const blob = await store.downloadExport(item.id)
  if (!blob) return
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = item.filename || `aima-ugc-voice-plaza-${item.id}.xlsx`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
  showNotice('Excel 导出文件已开始下载。')
}

/** 展示短时成功反馈，并只清理由本次调用写入的消息。 */
function showNotice(message: string): void {
  notice.value = message
  window.setTimeout(() => { if (notice.value === message) notice.value = null }, 2800)
}

/** 按每个 Shard 冻结目标数加权，避免大小不同的 Shard 被等权计算。 */
function analysisRunProgress(run: AnalysisContentRunResponse): number {
  const shards = run.shards ?? []
  if (run.target_count > 0 && shards.length > 0) {
    const weightedProgress = shards.reduce(
      (total, shard) => total + shard.target_count * shard.progress,
      0,
    )
    // 尚未进入有界调度窗口的目标视为 0%，避免新 Shard 创建后总进度倒退。
    return Math.max(0, Math.min(100, Math.round(weightedProgress / run.target_count)))
  }
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return Math.max(0, Math.min(100, Math.round(terminal * 100 / run.target_count)))
}

/** 用 Run 终态统计解释百分比，不把失败或取消伪装成成功。 */
function analysisRunProgressDetail(run: AnalysisContentRunResponse): string {
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return `${terminal} / ${run.target_count} 条已取得终态`
}
</script>

<template>
  <AppShell section-title="声音广场">
    <div class="voice-plaza-page">
      <AimaPageHeader
        title="声音广场"
        description="浏览全部渠道入库的用户声音，查看 AI 情感与完整标签结果"
      >
        <template #actions>
          <AimaButton
            icon="refresh"
            @click="refreshPage"
          >
            刷新数据
          </AimaButton>
          <AimaButton
            icon="ai"
            :disabled="store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : '可选择已选内容或全部数据进行打标'"
            @click="analysisOpen = true"
          >
            AI 打标
          </AimaButton>
          <AimaButton
            variant="primary"
            icon="download"
            @click="exportOpen = true"
          >
            导出记录
          </AimaButton>
        </template>
      </AimaPageHeader>

      <VoicePlazaFilters
        v-model:search="store.filters.search"
        v-model:platform="store.filters.platform"
        v-model:content-type="store.filters.contentType"
        v-model:analysis-status="store.filters.analysisStatus"
        v-model:relevance="store.filters.relevance"
        v-model:voice-type="store.filters.voiceType"
        v-model:sentiment="store.filters.sentiment"
        v-model:primary-label="store.filters.primaryLabel"
        v-model:secondary-label="store.filters.secondaryLabel"
        v-model:published-from="store.filters.publishedFrom"
        v-model:published-to="store.filters.publishedTo"
        v-model:source-identifier="store.filters.sourceIdentifier"
        v-model:vehicle-model-ids="store.filters.vehicleModelIds"
        :taxonomy="store.taxonomy"
        :taxonomy-loading="store.taxonomyLoading"
        @search="search"
        @reset="reset"
      />

      <AimaFeedbackBanner
        v-if="store.analysisConfigured === false"
        class="capability-warning"
        tone="warning"
      >
        <strong>AI 打标暂不可用：当前环境尚未配置可用的 LLM Runtime。</strong>
        <span>能力状态来自 GET /api/v1/content-analysis-capabilities；前端不读取 Secret、Base URL 或模型配置文件。</span>
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="store.taxonomyError"
        class="taxonomy-warning"
        tone="warning"
        role="alert"
      >
        <strong>分类配置暂不可用</strong>
        <span>{{ store.taxonomyError }}；依赖分类配置的筛选已禁用，内容列表和独立操作仍可使用。</span>
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="reviewNote"
        class="review-note"
        tone="info"
      >
        {{ reviewNote }}
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="store.listError || store.error"
        class="page-error"
        tone="error"
        role="alert"
      >
        <strong>{{ store.listError && store.items.length === 0 ? '加载声音广场失败' : '声音广场操作失败' }}</strong>
        <span>{{ store.listError ?? store.error }}</span>
      </AimaFeedbackBanner>

      <section
        v-if="activeAnalysisRuns.length && (!store.listError || store.items.length > 0)"
        class="active-analysis-runs"
        aria-label="AI 打标活动任务"
      >
        <header class="active-analysis-heading">
          <div>
            <strong>AI 打标任务</strong>
            <span>{{ activeAnalysisRuns.length }} 个活动 Run；历史与其它后台任务统一在任务中心查看。</span>
          </div>
          <button
            type="button"
            @click="taskCenter.openCenter()"
          >
            查看任务中心
          </button>
        </header>
        <article
          v-for="run in activeAnalysisRuns"
          :key="run.id"
        >
          <span
            class="run-status"
            :class="`run-status--${run.status}`"
          >{{ runStatusLabels[run.status] }}</span>
          <div class="run-info">
            <strong>Run #{{ run.sequence_no }} · {{ runStatusLabels[run.status] }}</strong>
            <small>{{ analysisRunProgressDetail(run) }}</small>
          </div>
          <TaskProgressBar
            compact
            :label="`AI Run #${run.sequence_no} 进度`"
            :value="analysisRunProgress(run)"
            :detail="analysisRunProgressDetail(run)"
          />
          <span class="run-counts">成功 {{ run.stats?.succeeded ?? 0 }} · 失败 {{ run.stats?.failed ?? 0 }}</span>
          <AimaButton
            v-if="run.status === 'queued' || run.status === 'running'"
            size="small"
            :disabled="store.cancellingAnalysisRunId === run.id"
            @click="cancelAnalysis(run.id)"
          >
            {{ store.cancellingAnalysisRunId === run.id ? '取消中…' : '取消 Run' }}
          </AimaButton>
        </article>
      </section>

      <div
        v-if="store.items.length > 0"
        class="list-heading"
      >
        <div class="selection-actions">
          <strong>声音记录</strong>
          <span>已加载 {{ store.items.length }} 条</span>
          <button
            v-if="selectedReviewIds.relevant.length"
            class="review-selected review-selected--relevant"
            type="button"
            :disabled="store.reviewingRelevance"
            @click="reviewSelected('relevant')"
          >
            批量标记为相关（{{ selectedReviewIds.relevant.length }}）
          </button>
          <button
            v-if="selectedReviewIds.irrelevant.length"
            class="review-selected review-selected--irrelevant"
            type="button"
            :disabled="store.reviewingRelevance"
            @click="reviewSelected('irrelevant')"
          >
            批量标记为不相关（{{ selectedReviewIds.irrelevant.length }}）
          </button>
          <button
            v-if="selectedReviewIds.inherit_ai.length"
            class="review-selected review-selected--undo"
            type="button"
            :disabled="store.reviewingRelevance"
            @click="reviewSelected('inherit_ai')"
          >
            批量撤销人工判断（{{ selectedReviewIds.inherit_ai.length }}）
          </button>
          <button
            v-if="store.selectedIds.length"
            class="selected-count"
            type="button"
            @click="store.clearSelection()"
          >
            已选 {{ store.selectedIds.length }} 条 · 清除
          </button>
        </div>
        <span>发布时间：最新优先</span>
      </div>

      <VoicePlazaTable
        :items="store.items"
        :loading="store.loading"
        :error="store.listError"
        :selected-ids="store.selectedIds"
        :reviewing="store.reviewingRelevance"
        @detail="store.openDetail"
        @toggle="store.toggleSelection"
        @toggle-all="store.toggleVisibleSelection"
        @review="reviewSingle"
      />

      <div
        v-if="store.items.length > 0"
        class="pagination"
      >
        <div class="count-tools">
          <span>游标分页不会虚构总页数</span>
          <span v-if="store.contentCount?.count != null">
            {{ store.contentCount.count_kind === 'estimated' ? '估算' : '精确' }} {{ store.contentCount.count }} 条
          </span>
          <span v-else-if="store.contentCount?.truncated">
            当前范围超过有界精确计数上限
          </span>
          <span v-else-if="store.contentCount?.count_mode === 'estimated'">
            当前筛选不提供可靠估算
          </span>
          <button
            type="button"
            :disabled="store.countLoading"
            @click="store.refreshCount('exact')"
          >
            有界精确总数
          </button>
          <button
            type="button"
            :disabled="store.countLoading"
            @click="store.refreshCount('estimated')"
          >
            快速估算
          </button>
        </div>
        <AimaButton
          size="small"
          :disabled="!store.hasMore || store.loadingNext"
          @click="store.loadNext()"
        >
          {{ store.loadingNext ? '加载中…' : store.hasMore ? '加载更多 →' : '已加载全部' }}
        </AimaButton>
      </div>

      <ContentDetailDrawer
        v-model="detailOpen"
        :item="store.detail"
        :loading="store.loadingDetail"
        :taxonomy="store.taxonomy"
        :saving="store.reviewingDetail"
        @review-vehicles="store.reviewDetailVehicles"
        @review-analysis="store.reviewDetailAnalysis"
      />
      <AnalysisSubmitDialog
        v-model="analysisOpen"
        :selected-count="store.selectedIds.length"
        :preview="store.analysisPreview"
        :previewing="store.previewingAnalysis"
        :submitting="store.submittingAnalysis"
        @preview="store.previewAnalysis"
        @submit="submitAnalysis"
      />
      <DataExportDialog
        v-model="exportOpen"
        :selected-count="store.selectedIds.length"
        :page-count="store.items.length"
        :items="store.exports"
        :column-catalog="store.exportColumnCatalog"
        :submitting="store.submittingExport"
        @submit="submitExport"
        @refresh="store.refreshExports"
        @download="download"
      />
      <AimaFeedbackBanner
        v-if="notice"
        class="notice"
        tone="success"
      >
        {{ notice }}
      </AimaFeedbackBanner>
    </div>
  </AppShell>
</template>

<style scoped>
.voice-plaza-page { display: grid; gap: 10px; }
.capability-warning strong,
.capability-warning span,
.taxonomy-warning strong,
.taxonomy-warning span,
.page-error strong,
.page-error span { display: block; }
.capability-warning strong,
.taxonomy-warning strong,
.page-error strong { margin-bottom: 2px; font-size: 11px; }
.capability-warning span,
.taxonomy-warning span,
.page-error span { font-size: 10px; }
.active-analysis-runs { display: grid; gap: 7px; padding: 10px 14px; border: 1px solid #dbe7ff; border-radius: var(--aima-radius-control); background: #fbfdff; }
.active-analysis-heading { display: flex; min-height: 22px; align-items: center; justify-content: space-between; gap: 16px; }
.active-analysis-heading > div { display: flex; min-width: 0; align-items: baseline; gap: 8px; }
.active-analysis-heading strong { color: var(--aima-text); font-size: 12px; }
.active-analysis-heading span { overflow: hidden; color: var(--aima-text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.active-analysis-heading button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; white-space: nowrap; }
.active-analysis-heading button:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 2px; }
.active-analysis-runs article { display: grid; min-height: 36px; grid-template-columns: auto minmax(180px, 250px) minmax(220px, 1fr) auto auto; align-items: center; gap: 10px; }
.run-status { display: inline-flex; min-height: 20px; align-items: center; padding: 2px 8px; border-radius: 4px; color: #1677ff; background: #e8f3ff; font-size: 10px; font-weight: 500; }
.run-status--cancelling { color: var(--aima-text-muted); background: #f2f4f7; }
.run-info { display: grid; min-width: 0; gap: 2px; }
.run-info strong,
.run-info small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.run-info strong { color: var(--aima-text); font-size: 11px; font-weight: 500; }
.run-info small { color: var(--aima-text-muted); font-size: 9px; }
.active-analysis-runs article :deep(.task-progress) { width: 100%; }
.active-analysis-runs article :deep(.task-progress__heading) { display: none; }
.active-analysis-runs article :deep(.task-progress__track) { height: 6px; }
.run-counts { color: var(--aima-text-muted); font-size: 10px; white-space: nowrap; }
.list-heading { display: flex; min-height: 36px; align-items: center; justify-content: space-between; gap: 16px; }
.selection-actions { display: flex; min-width: 0; flex-wrap: wrap; align-items: center; gap: 8px; }
.list-heading strong { color: var(--aima-text); font-size: 14px; }
.list-heading span { color: var(--aima-text-muted); font-size: 11px; }
.selection-actions button { min-height: 20px; padding: 2px 8px; border: 0; border-radius: 4px; cursor: pointer; font-size: 10px; }
.review-selected--relevant { color: #12804b; background: #e8fff3; }
.review-selected--irrelevant { color: #f04438; background: #fff1f0; }
.review-selected--undo { color: var(--aima-text-muted); background: #f2f4f7; }
.selected-count { color: var(--aima-primary); background: var(--aima-primary-soft); }
.selection-actions button:disabled { cursor: not-allowed; opacity: .55; }
.pagination { display: flex; min-height: 36px; align-items: center; justify-content: space-between; gap: 20px; color: var(--aima-text-muted); font-size: 11px; }
.count-tools { display: flex; align-items: center; gap: 8px; }
.count-tools button { padding: 3px 7px; border: 1px solid var(--aima-border); border-radius: 4px; color: var(--aima-text-secondary); background: var(--aima-surface); cursor: pointer; font-size: 10px; }
.count-tools button:disabled { cursor: wait; opacity: .55; }
.pagination :deep(.aima-button) { height: 34px; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; min-width: 280px; transform: translateX(-50%); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
@media (max-width: 1280px) {
  .active-analysis-runs article { grid-template-columns: auto minmax(180px, 1fr) minmax(180px, 1fr); }
  .run-counts { grid-column: 2; }
}
</style>
