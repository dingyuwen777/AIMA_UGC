<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '../../../../app/layouts/AppShell.vue'
import type {
  AnalysisContentRunResponse,
  ContentRelevanceReviewResponse,
  DataExportResponse,
} from '../../../../generated/api/client'
import TaskProgressBar from '../../../../shared/TaskProgressBar.vue'
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
const route = useRoute()
const analysisOpen = ref(false)
const exportOpen = ref(false)
const notice = ref<string | null>(null)
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

async function refreshPage(): Promise<void> {
  await Promise.all([
    store.refresh(),
    store.refreshExports(),
    store.refreshAnalysisCapabilities(),
    store.refreshAnalysisRuns(),
  ])
}

async function search(): Promise<void> {
  store.clearSelection()
  await store.refresh()
}

async function reset(): Promise<void> {
  store.resetFilters()
  await store.refresh()
}

function relevanceNotice(
  decision: RelevanceReviewDecision,
  result: ContentRelevanceReviewResponse,
): string {
  const unchanged = result.unchanged_count > 0 ? `，${result.unchanged_count} 条无需变化` : ''
  if (decision === 'relevant') return `已人工标记 ${result.changed_count} 条内容为相关${unchanged}。`
  if (decision === 'irrelevant') return `已人工标记 ${result.changed_count} 条内容为不相关${unchanged}。`
  return `已撤销 ${result.changed_count} 条人工相关性判断${unchanged}。`
}

async function reviewSingle(
  contentId: string,
  decision: RelevanceReviewDecision,
): Promise<void> {
  const result = await store.reviewRelevance([contentId], decision)
  if (result) showNotice(relevanceNotice(decision, result))
}

async function reviewSelected(decision: RelevanceReviewDecision): Promise<void> {
  const contentIds = selectedReviewIds.value[decision]
  const result = await store.reviewRelevance(contentIds, decision)
  if (result) showNotice(relevanceNotice(decision, result))
}

async function submitAnalysis(): Promise<void> {
  const count = await store.confirmAnalysis()
  if (count === null) return
  analysisOpen.value = false
  showNotice(`已创建 AI Analysis Run，冻结 ${count} 条内容。`)
}

async function cancelAnalysis(runId: string): Promise<void> {
  if (await store.cancelRun(runId)) showNotice('已请求取消 Analysis Run。')
}

async function submitExport(scope: 'query' | 'selected' | 'page'): Promise<void> {
  const count = await store.createExport(scope)
  if (count === null) return
  showNotice(`已创建 Excel 导出 Job，冻结 ${count} 条内容。`)
}

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
    <div class="page-header">
      <div><h1>声音广场</h1><p>浏览全部渠道入库的用户声音，查看 AI 情感与完整标签结果</p></div><div class="page-actions">
        <button
          type="button"
          @click="refreshPage"
        >
          ↻&nbsp; 刷新数据
        </button><button
          type="button"
          :disabled="store.selectedIds.length === 0 || store.selectedIds.length > 1000 || store.analysisConfigured !== true"
          :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : store.selectedIds.length === 0 ? '请先选择需要打标的内容' : store.selectedIds.length > 1000 ? '单次最多选择 1000 条内容' : undefined"
          @click="analysisOpen = true"
        >
          ◇&nbsp; AI 打标
        </button><button
          class="primary"
          type="button"
          @click="exportOpen = true"
        >
          ⇩&nbsp; 导出记录
        </button>
      </div>
    </div>

    <div
      v-if="store.analysisConfigured === false"
      class="capability-warning"
      role="status"
    >
      AI 打标暂不可用：当前环境尚未配置可用的 LLM Runtime。请完成 LLM 配置并重启后端；本地源码调试可编辑根目录 <code>env.local</code>。
    </div>

    <VoicePlazaFilters
      v-model:search="store.filters.search"
      v-model:platform="store.filters.platform"
      v-model:content-type="store.filters.contentType"
      v-model:analysis-status="store.filters.analysisStatus"
      v-model:relevance="store.filters.relevance"
      v-model:sentiment="store.filters.sentiment"
      v-model:primary-label="store.filters.primaryLabel"
      v-model:secondary-label="store.filters.secondaryLabel"
      v-model:published-from="store.filters.publishedFrom"
      v-model:published-to="store.filters.publishedTo"
      v-model:source-identifier="store.filters.sourceIdentifier"
      @search="search"
      @reset="reset"
    />
    <div
      v-if="reviewNote"
      class="review-note"
      role="status"
    >
      {{ reviewNote }}
    </div>
    <div
      v-if="store.error"
      class="page-error"
      role="alert"
    >
      !&nbsp; {{ store.error }}
    </div>
    <section
      v-if="store.analysisRuns.length"
      class="run-history"
      aria-label="AI Analysis Run 历史"
    >
      <header><strong>AI Analysis Run 历史</strong><span>不同 Run 结果均保留；Current 按创建顺序选择</span></header>
      <article
        v-for="run in store.analysisRuns"
        :key="run.id"
      >
        <div><strong>Run #{{ run.sequence_no }} · {{ runStatusLabels[run.status] }}</strong><span>{{ run.target_count }} 条 · {{ run.shard_count }} Shard · {{ run.model }}</span><small v-if="run.error_code">{{ run.error_code }}</small></div><TaskProgressBar
          compact
          :label="`AI Run #${run.sequence_no} 进度`"
          :value="analysisRunProgress(run)"
          :detail="analysisRunProgressDetail(run)"
        /><span>完成 {{ run.stats?.succeeded ?? 0 }} / 失败 {{ run.stats?.failed ?? 0 }} / 取消 {{ run.stats?.cancelled ?? 0 }}</span><button
          v-if="run.status === 'queued' || run.status === 'running'"
          type="button"
          :disabled="store.cancellingAnalysisRunId === run.id"
          @click="cancelAnalysis(run.id)"
        >
          {{ store.cancellingAnalysisRunId === run.id ? '取消中…' : '取消 Run' }}
        </button>
      </article>
    </section>

    <div class="list-heading">
      <div>
        <strong>声音记录</strong><span>已加载 {{ store.items.length }} 条</span><button
          v-if="selectedReviewIds.relevant.length"
          class="review-selected review-selected--relevant"
          type="button"
          :disabled="store.reviewingRelevance"
          @click="reviewSelected('relevant')"
        >
          批量标记为相关（{{ selectedReviewIds.relevant.length }}）
        </button><button
          v-if="selectedReviewIds.irrelevant.length"
          class="review-selected review-selected--irrelevant"
          type="button"
          :disabled="store.reviewingRelevance"
          @click="reviewSelected('irrelevant')"
        >
          批量标记为不相关（{{ selectedReviewIds.irrelevant.length }}）
        </button><button
          v-if="selectedReviewIds.inherit_ai.length"
          class="review-selected review-selected--undo"
          type="button"
          :disabled="store.reviewingRelevance"
          @click="reviewSelected('inherit_ai')"
        >
          批量撤销人工判断（{{ selectedReviewIds.inherit_ai.length }}）
        </button><button
          v-if="store.selectedIds.length"
          type="button"
          @click="store.clearSelection()"
        >
          已选 {{ store.selectedIds.length }} 条 ×
        </button>
      </div><span>发布时间：最新优先</span>
    </div>
    <VoicePlazaTable
      :items="store.items"
      :loading="store.loading"
      :selected-ids="store.selectedIds"
      :reviewing="store.reviewingRelevance"
      @detail="store.openDetail"
      @toggle="store.toggleSelection"
      @toggle-all="store.toggleVisibleSelection"
      @review="reviewSingle"
    />
    <div class="pagination">
      <span>游标分页不会虚构总页数</span><button
        type="button"
        :disabled="!store.hasMore || store.loadingNext"
        @click="store.loadNext()"
      >
        {{ store.loadingNext ? '加载中…' : store.hasMore ? '加载更多 →' : '已加载全部' }}
      </button>
    </div>

    <ContentDetailDrawer
      v-model="detailOpen"
      :item="store.detail"
      :loading="store.loadingDetail"
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
      :submitting="store.submittingExport"
      @submit="submitExport"
      @refresh="store.refreshExports"
      @download="download"
    />
    <div
      v-if="notice"
      class="notice"
      role="status"
    >
      ✓ {{ notice }}
    </div>
  </AppShell>
</template>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h1 { margin: 0; color: #172033; font-size: 25px; }
.page-header p { margin: 7px 0 0; color: #6e7789; font-size: 13px; }
.page-actions { display: flex; gap: 10px; }
.page-actions button { height: 42px; padding: 0 17px; border: 1px solid #d7dce5; border-radius: 7px; color: #384153; background: #fff; cursor: pointer; }
.page-actions .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); box-shadow: 0 5px 14px rgb(245 0 87 / 18%); }
.page-actions button:disabled { opacity: .55; cursor: default; }
.capability-warning { margin-top: 14px; padding: 11px 14px; border: 1px solid #f2d48a; border-radius: 7px; color: #7f5d18; background: #fff9e9; font-size: 12px; line-height: 1.55; }
.capability-warning code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.review-note { margin-top: 12px; padding: 11px 14px; border: 1px solid #bfd5f5; border-radius: 7px; color: #32618f; background: #f2f7fd; font-size: 12px; line-height: 1.6; }
.page-error { margin-top: 14px; padding: 11px 14px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 13px; }
.run-history { margin-top: 14px; overflow: hidden; border: 1px solid #dfe3ea; border-radius: 8px; background: #fff; }
.run-history header, .run-history article { display: flex; align-items: center; gap: 16px; justify-content: space-between; padding: 11px 14px; }
.run-history header { background: #f7f8fa; }
.run-history header span, .run-history article span { color: #768092; font-size: 12px; }
.run-history article { border-top: 1px solid #edf0f4; }
.run-history article div { display: grid; gap: 4px; }
.run-history article :deep(.task-progress) { width: min(300px, 30vw); }
.run-history article button { padding: 6px 10px; border: 1px solid #d7dce5; border-radius: 5px; color: #b4232d; background: #fff; cursor: pointer; }
.run-history article button:disabled { opacity: .55; cursor: default; }
.list-heading { display: flex; align-items: center; justify-content: space-between; margin: 22px 0 11px; }
.list-heading div { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.list-heading strong { font-size: 17px; }
.list-heading span { color: #768092; font-size: 12px; }
.list-heading > span { padding: 8px 11px; border: 1px solid #dfe3ea; border-radius: 6px; background: #fff; }
.list-heading button { padding: 5px 9px; border: 0; border-radius: 5px; color: var(--aima-primary); background: var(--aima-primary-soft); cursor: pointer; }
.list-heading button.review-selected--relevant { color: #12804b; background: #eaf8f1; }
.list-heading button.review-selected--irrelevant { color: #b4232d; background: #fff0f1; }
.list-heading button.review-selected--undo { color: #586174; background: #f1f3f6; }
.list-heading button:disabled { cursor: not-allowed; opacity: .55; }
.pagination { display: flex; min-height: 70px; align-items: center; justify-content: flex-end; gap: 20px; color: #858e9d; font-size: 11px; }
.pagination button { min-width: 120px; height: 38px; border: 1px solid var(--aima-primary); border-radius: 6px; color: var(--aima-primary); background: #fff; cursor: pointer; }
.pagination button:disabled { border-color: #dfe3ea; color: #a4acba; cursor: default; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; padding: 11px 18px; border: 1px solid #a9e3c7; border-radius: 7px; color: #12804b; background: #effbf5; box-shadow: 0 8px 24px rgb(22 29 43 / 12%); transform: translateX(-50%); }
</style>
