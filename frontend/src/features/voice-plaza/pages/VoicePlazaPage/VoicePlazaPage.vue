<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '../../../../app/layouts/AppShell.vue'
import {
  PlatformName,
  type AnalysisContentRunResponse,
  type ContentAnalysisManualReviewRequest,
  type ContentRelevanceReviewResponse,
  type DataExportResponse,
  type ExportColumnKey,
} from '../../../../generated/api/client'
import TaskProgressBar from '../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../../shared/ui/AimaPageHeader.vue'
import { useTransientNotice } from '../../../../shared/ui/useTransientNotice'
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
const { message: notice, show: showNotice } = useTransientNotice()
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
  get: () => store.detailId !== null,
  set: (open: boolean) => { if (!open) store.closeDetail() },
})

/** 把 Router Query 的单值/数组统一为非空字符串数组，供工作台深链恢复使用。 */
function routeValues(value: unknown): string[] {
  if (typeof value === 'string') return value.trim() ? [value.trim()] : []
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
}

/** 从真实可表达的声音广场筛选字段恢复工作台深链，不解析未知参数。 */
function hydrateRouteFilters(): void {
  const deepLinkKeys = [
    'source_identifier', 'sentiment', 'voice_type',
    'primary_labels', 'secondary_labels', 'primary_label', 'secondary_label',
    'published_from', 'published_to', 'platform', 'brand_ids', 'vehicle_model_ids', 'content_id',
  ]
  if (deepLinkKeys.some((key) => routeValues(route.query[key]).length > 0)) {
    // 深链是完整入口；会话里遗留的其他条件不能隐式排除本次目标内容。
    store.resetFilters()
  }
  let changed = false
  const setString = (
    queryKey: string,
    filterKey: 'sourceIdentifier' | 'publishedFrom' | 'publishedTo',
  ): void => {
    const value = routeValues(route.query[queryKey])[0]
    if (!value) return
    store.filters[filterKey] = value
    changed = true
  }

  setString('source_identifier', 'sourceIdentifier')
  setString('published_from', 'publishedFrom')
  setString('published_to', 'publishedTo')

  const platforms = routeValues(route.query.platform).filter(
    (item): item is PlatformName => Object.values(PlatformName).includes(item as PlatformName),
  )
  if (platforms.length) {
    store.filters.platforms = platforms
    changed = true
  }
  const voiceTypes = routeValues(route.query.voice_type)
  if (voiceTypes.length) {
    store.filters.voiceTypes = voiceTypes
    changed = true
  }
  const sentiments = routeValues(route.query.sentiment)
  if (sentiments.length) {
    store.filters.sentiments = sentiments
    changed = true
  }
  const primaryLabels = routeValues(route.query.primary_labels)
  const legacyPrimaryLabels = routeValues(route.query.primary_label)
  const restoredPrimaryLabels = primaryLabels.length ? primaryLabels : legacyPrimaryLabels
  const secondaryLabels = routeValues(route.query.secondary_labels)
  const legacySecondaryLabels = routeValues(route.query.secondary_label)
  const restoredSecondaryLabels = secondaryLabels.length ? secondaryLabels : legacySecondaryLabels
  if (restoredPrimaryLabels.length || restoredSecondaryLabels.length) {
    store.restoreLabelFilters(
      restoredPrimaryLabels,
      restoredSecondaryLabels,
      (primaryLabels.length === 0 && legacyPrimaryLabels.length > 0)
        || (secondaryLabels.length === 0 && legacySecondaryLabels.length > 0),
    )
    changed = true
  }

  const brandIds = routeValues(route.query.brand_ids)
  if (brandIds.length) {
    store.filters.brandIds = brandIds
    changed = true
  }
  const vehicleModelIds = routeValues(route.query.vehicle_model_ids)
  if (vehicleModelIds.length) {
    store.filters.vehicleModelIds = vehicleModelIds
    changed = true
  }

  if (changed) store.applyFilters()
}

/** 工作台笔记深链直接打开对应 Content 详情，跨分页时仍能定位真实记录。 */
watch(() => route.query.content_id, (value) => {
  const contentId = routeValues(value)[0]
  if (!contentId || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(contentId)) return
  if (store.detailId !== contentId) void store.openDetail(contentId)
}, { immediate: true })

onMounted(() => {
  hydrateRouteFilters()
  void refreshPage().finally(() => store.startPolling())
})
onBeforeUnmount(() => {
  store.cancelCount()
  store.stopPolling()
})

/** 首先展示最新倒序第一页，再在后台加载不会影响首屏的目录与任务资源。 */
async function refreshPage(): Promise<void> {
  await store.refreshResults()
  void Promise.allSettled([
    store.refreshTaxonomy(),
    store.refreshFilterOptions(),
    store.refreshExports(),
    store.refreshAnalysisCapabilities(),
    store.refreshAnalysisRuns(),
  ])
}

/** 提交当前筛选并清空旧选择，避免跨查询误操作。 */
async function search(): Promise<void> {
  store.applyFilters()
  await store.refreshResults()
}

/** 恢复默认筛选并重新获取第一页。 */
async function reset(): Promise<void> {
  store.resetFilters()
  await store.refreshResults()
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

/** 详情人工车型结论成功后复用页面统一的 3 秒反馈。 */
async function reviewDetailVehicles(
  vehicleModelIds: string[],
  unlockExisting: boolean,
): Promise<void> {
  if (await store.reviewDetailVehicles(vehicleModelIds, unlockExisting)) {
    showNotice('车型人工结论已保存；后续自动识别不会覆盖当前人工结果。')
  }
}

/** 详情分析人工纠正成功后复用页面统一的 3 秒反馈。 */
async function reviewDetailAnalysis(
  request: Omit<ContentAnalysisManualReviewRequest, 'content_version'>,
): Promise<void> {
  if (await store.reviewDetailAnalysis(request)) {
    showNotice('分析人工纠正已保存；如需替换已确认结果，请先确认解除当前人工结论。')
  }
}

/** 使用预检冻结信息确认创建 Analysis Run，并同步全局任务中心。 */
async function submitAnalysis(): Promise<void> {
  const count = await store.confirmAnalysis()
  if (count === null) return
  analysisOpen.value = false
  showNotice(`已创建 AI 分析任务，将处理 ${count} 条内容。`)
}

/** 请求取消仍处于可取消状态的 Analysis Run，并同步全局任务中心。 */
async function cancelAnalysis(runId: string): Promise<void> {
  if (await store.cancelRun(runId)) {
    showNotice('已请求取消 AI 分析任务。')
  }
}

/** 创建 selected/page/query 三种既有范围之一的 Excel 导出。 */
async function submitExport(
  scope: 'query' | 'selected' | 'page',
  columns: ExportColumnKey[],
): Promise<void> {
  const count = await store.createExport(scope, columns)
  if (count === null) return
  showNotice(`已创建 Excel 导出任务，将导出 ${count} 条内容。`)
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

/** 按已持久化终态数量显示进度，与明细计数保持一致。 */
function analysisRunProgress(run: AnalysisContentRunResponse): number {
  if (run.target_count <= 0) return 0
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return Math.max(0, Math.min(100, Math.round(terminal * 100 / run.target_count)))
}

/** 用运行统计生成业务可读进度，不把失败或取消伪装成成功。 */
function analysisRunProgressDetail(run: AnalysisContentRunResponse): string {
  const stats = run.stats
  const terminal = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) +
    (stats?.cancelled ?? 0) + (stats?.stale ?? 0)
  return `已处理 ${terminal} / ${run.target_count} 条`
}
</script>

<template>
  <AppShell section-title="声音广场">
    <div class="voice-plaza-page">
      <AimaPageHeader
        title="声音广场"
        description="浏览全平台爱玛相关内容，定位值得关注的真实用户声音"
      >
        <template #actions>
          <AimaButton
            size="small"
            :disabled="store.analysisConfigured !== true"
            :title="store.analysisConfigured === false ? 'AI 分析尚未配置' : store.analysisConfigured === null ? '正在检查 AI 分析是否可用' : '可选择已选内容或全部数据进行分析'"
            @click="analysisOpen = true"
          >
            AI 分析
          </AimaButton>
          <AimaButton
            variant="primary"
            size="small"
            @click="exportOpen = true"
          >
            导出记录
          </AimaButton>
        </template>
      </AimaPageHeader>

      <VoicePlazaFilters
        v-model:search="store.filters.search"
        v-model:platforms="store.filters.platforms"
        v-model:analysis-status="store.filters.analysisStatus"
        v-model:relevance="store.filters.relevance"
        v-model:voice-types="store.filters.voiceTypes"
        v-model:sentiments="store.filters.sentiments"
        v-model:primary-labels="store.filters.primaryLabels"
        v-model:secondary-labels="store.filters.secondaryLabels"
        v-model:published-from="store.filters.publishedFrom"
        v-model:published-to="store.filters.publishedTo"
        v-model:source-identifier="store.filters.sourceIdentifier"
        v-model:brand-ids="store.filters.brandIds"
        v-model:vehicle-model-ids="store.filters.vehicleModelIds"
        :filter-options="store.filterOptions"
        :filter-options-loading="store.filterOptionsLoading"
        :legacy-label-compatibility="store.legacyLabelCompatibility"
        @search="search"
        @reset="reset"
      />

      <AimaFeedbackBanner
        v-if="store.analysisConfigured === false"
        class="capability-warning"
        tone="warning"
      >
        <strong>AI 分析暂不可用：管理员尚未完成 AI 模型配置。</strong>
        <span>请联系管理员完成模型配置后重试；内容浏览、筛选和人工复核不受影响。</span>
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="store.filterOptionsError"
        class="taxonomy-warning"
        tone="warning"
        role="alert"
      >
        <strong>部分动态筛选项暂不可用</strong>
        <span>平台、相关性和状态仍可筛选；情感、标签等动态目录可稍后重试。</span>
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="store.taxonomyError"
        class="taxonomy-warning"
        tone="warning"
        role="alert"
      >
        <strong>当前 AI 分析规则暂不可用</strong>
        <span>分析结果人工纠正已暂时停用；内容浏览与筛选仍可使用。</span>
      </AimaFeedbackBanner>
      <AimaFeedbackBanner
        v-if="store.listError || store.error"
        class="page-error"
        tone="error"
        role="alert"
      >
        <strong>{{ store.listError && store.items.length === 0 ? '暂时无法加载声音记录' : '操作未完成' }}</strong>
        <span>{{ store.listError && store.items.length === 0 ? '请检查网络或服务状态后重试。' : '当前页面状态已保留，请稍后重试。' }}</span>
        <AimaButton
          size="small"
          @click="refreshPage"
        >
          刷新数据
        </AimaButton>
      </AimaFeedbackBanner>

      <section
        v-if="activeAnalysisRuns.length && (!store.listError || store.items.length > 0)"
        class="active-analysis-runs"
        aria-label="AI 分析活动任务"
      >
        <header class="active-analysis-heading">
          <div>
            <strong>AI 分析任务</strong>
            <span>{{ activeAnalysisRuns.length }} 个任务正在处理；历史任务统一在任务中心查看。</span>
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
            <strong>AI 分析 · {{ runStatusLabels[run.status] }}</strong>
            <small>{{ analysisRunProgressDetail(run) }}</small>
          </div>
          <TaskProgressBar
            compact
            label="AI 分析进度"
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
            {{ store.cancellingAnalysisRunId === run.id ? '取消中…' : '取消任务' }}
          </AimaButton>
        </article>
      </section>

      <div
        class="list-heading"
      >
        <div class="selection-actions">
          <div
            v-if="store.items.length === 0"
            class="count-summary"
          >
            <span v-if="store.contentCount?.count != null">{{ store.contentCount.count_kind === 'estimated' ? '约' : '共' }} <strong>{{ store.contentCount.count.toLocaleString('zh-CN') }} 条</strong></span>
            <span v-else-if="store.countLoading">总数统计中…</span>
            <span
              v-else-if="store.countError"
              class="count-error"
            >
              总数统计失败
              <button
                class="count-retry"
                type="button"
                @click="store.refreshCount('estimated')"
              >
                重试总数
              </button>
            </span>
            <span v-else-if="store.contentCount?.count_kind === 'none'">总数数据准备中…</span>
            <span v-else>总数暂不可用</span>
          </div>
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
            class="selected-count"
            :class="{ 'selected-count--empty': store.selectedIds.length === 0 }"
            type="button"
            @click="store.clearSelection()"
          >
            {{ store.selectedIds.length ? `已选 ${store.selectedIds.length} 条 · 清除` : '已选 0 条' }}
          </button>
        </div>
      </div>

      <VoicePlazaTable
        :items="store.items"
        :loading="store.loading"
        :error="store.listError"
        :selected-ids="store.selectedIds"
        :reviewing="store.reviewingRelevance"
        :sort-by="store.sortBy"
        :sort-direction="store.sortDirection"
        @sort="store.changeSort"
        @detail="store.openDetail"
        @toggle="store.toggleSelection"
        @toggle-all="store.toggleVisibleSelection"
        @review="reviewSingle"
      />

      <div
        v-if="store.items.length > 0"
        class="pagination"
      >
        <span class="pagination-count">
          <span v-if="store.contentCount?.count != null">{{ store.contentCount.count_kind === 'estimated' ? '约' : '共' }} {{ store.contentCount.count.toLocaleString('zh-CN') }} 条</span>
          <span v-else-if="store.countLoading">总数统计中…</span>
          <span
            v-else-if="store.countError"
            class="count-error"
          >总数统计失败</span>
          <span v-else-if="store.contentCount?.count_kind === 'none'">总数数据准备中…</span>
          <span v-else>总数暂不可用</span>
          <small>当前已加载 {{ store.items.length }} 条</small>
        </span>
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
        :error="store.detailError"
        :save-error="store.error"
        :taxonomy="store.taxonomy"
        :saving="store.reviewingDetail"
        :comment-roots="store.commentRoots"
        :comment-replies="store.commentReplies"
        :comment-reply-states="store.commentReplyStates"
        :comments-loading="store.commentsLoading"
        :comments-loading-next="store.commentsLoadingNext"
        :comments-error="store.commentsError"
        :comments-has-more="store.commentsHasMore"
        :comments-total-count="store.commentsTotalCount"
        :comments-ingested-total-count="store.commentsIngestedTotalCount"
        @retry="store.detailId && store.openDetail(store.detailId)"
        @retry-comments="store.loadCommentRoots(true)"
        @load-more-comments="store.loadCommentRoots()"
        @load-comment-replies="store.loadCommentReplies"
        @review="reviewSingle"
        @review-vehicles="reviewDetailVehicles"
        @review-analysis="reviewDetailAnalysis"
      />
      <AnalysisSubmitDialog
        v-model="analysisOpen"
        :selected-count="store.selectedIds.length"
        :preview="store.analysisPreview"
        :previewing="store.previewingAnalysis"
        :error="store.error"
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
        :error="store.error"
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
.voice-plaza-page { display: grid; gap: 20px; }
.voice-plaza-page :deep(.aima-page-header) { flex-wrap: nowrap; align-items: center; }
.voice-plaza-page :deep(.aima-page-header h1) { font-weight: 700; }
.voice-plaza-page :deep(.aima-page-header p) { margin-top: 6px; }
.voice-plaza-page :deep(.aima-page-actions) { flex: none; }
.voice-plaza-page :deep(.aima-page-actions .aima-button.is-small) {
  min-height: 32px;
  font-size: 13px;
  font-weight: 500;
}
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
.selection-actions button { min-height: 20px; padding: 2px 8px; border: 0; border-radius: 4px; cursor: pointer; font-size: 10px; }
.review-selected--relevant { color: #12804b; background: #e8fff3; }
.review-selected--irrelevant { color: #f04438; background: #fff1f0; }
.review-selected--undo { color: var(--aima-text-muted); background: #f2f4f7; }
.selected-count { color: var(--aima-primary); background: var(--aima-primary-soft); }
.selected-count--empty { color: var(--aima-text-disabled); background: var(--aima-color-bg-hover); }
.selection-actions button:disabled { cursor: not-allowed; opacity: .55; }
.pagination { display: flex; min-height: 36px; align-items: center; justify-content: space-between; gap: 20px; color: var(--aima-text-muted); font-size: 11px; }
.pagination-count { display: flex; align-items: baseline; gap: 8px; }
.count-summary { display: flex; min-width: 0; align-items: baseline; gap: 8px; }
.count-summary strong { color: var(--aima-primary); }
.count-summary .count-error { color: var(--aima-danger); }
.count-retry { color: var(--aima-danger); background: var(--aima-color-error-bg); }
.pagination-count .count-error { color: var(--aima-danger); }
.pagination-count small { color: var(--aima-text-disabled); font-size: 10px; }
.pagination :deep(.aima-button) { height: 34px; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; min-width: 280px; transform: translateX(-50%); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
@media (max-width: 1280px) {
  .active-analysis-runs article { grid-template-columns: auto minmax(180px, 1fr) minmax(180px, 1fr); }
  .run-counts { grid-column: 2; }
}
</style>
