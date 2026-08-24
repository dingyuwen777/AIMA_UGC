<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '../../../../app/layouts/AppShell.vue'
import type { DataExportResponse, JobStatusResponse } from '../../../../generated/api/client'
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
const reviewMode = computed(() => store.filters.relevance === 'irrelevant')
const jobStatusLabels: Record<JobStatusResponse['status'], string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
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

async function reviewSingle(contentId: string): Promise<void> {
  const count = await store.reviewRelevance([contentId])
  if (count !== null) showNotice(`已人工标记 ${count} 条内容为相关。`)
}

async function reviewSelected(): Promise<void> {
  const count = await store.reviewRelevance([...store.selectedIds])
  if (count !== null) showNotice(`已人工标记 ${count} 条内容为相关。`)
}

async function submitAnalysis(scope: 'query' | 'selected'): Promise<void> {
  const count = await store.createAnalysis(scope)
  if (count === null) return
  analysisOpen.value = false
  showNotice(`已创建 AI 分析 Job，冻结 ${count} 条内容。`)
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
          :disabled="store.items.length === 0 || store.analysisConfigured !== true"
          :title="store.analysisConfigured === false ? '当前环境尚未配置 AI 模型' : store.analysisConfigured === null ? '正在确认 AI 运行配置' : undefined"
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
      v-if="reviewMode"
      class="review-note"
      role="status"
    >
      当前只显示 AI 判定不相关、且尚未被人工纳入的内容。人工标记为相关后，AI 原始判断仍保留用于审计，该内容会按当前版本进入默认业务数据。
    </div>
    <div
      v-if="store.error"
      class="page-error"
      role="alert"
    >
      !&nbsp; {{ store.error }}
    </div>
    <div
      v-if="store.analysisJob"
      class="job-banner"
      :class="`job-banner--${store.analysisJob.status}`"
    >
      <span>AI 分析 Job：{{ jobStatusLabels[store.analysisJob.status] }} · {{ store.analysisJob.progress }}%</span><span v-if="store.analysisJob.error_code">{{ store.analysisJob.error_code }}</span>
    </div>

    <div class="list-heading">
      <div>
        <strong>声音记录</strong><span>已加载 {{ store.items.length }} 条</span><button
          v-if="reviewMode && store.selectedIds.length"
          class="review-selected"
          type="button"
          :disabled="store.reviewingRelevance"
          @click="reviewSelected"
        >
          批量标记为相关
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
      :review-mode="reviewMode"
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
      :submitting="store.submittingAnalysis"
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
.job-banner { display: flex; justify-content: space-between; margin-top: 12px; padding: 10px 14px; border: 1px solid #bfd5f5; border-radius: 7px; color: #32618f; background: #f2f7fd; font-size: 12px; }
.job-banner--failed { border-color: #ffc7cc; color: #b4232d; background: #fff5f6; }
.job-banner--succeeded { border-color: #afe0c6; color: #12804b; background: #effbf5; }
.list-heading { display: flex; align-items: center; justify-content: space-between; margin: 22px 0 11px; }
.list-heading div { display: flex; align-items: center; gap: 10px; }
.list-heading strong { font-size: 17px; }
.list-heading span { color: #768092; font-size: 12px; }
.list-heading > span { padding: 8px 11px; border: 1px solid #dfe3ea; border-radius: 6px; background: #fff; }
.list-heading button { padding: 5px 9px; border: 0; border-radius: 5px; color: var(--aima-primary); background: var(--aima-primary-soft); cursor: pointer; }
.list-heading button.review-selected { color: #12804b; background: #eaf8f1; }
.list-heading button:disabled { cursor: not-allowed; opacity: .55; }
.pagination { display: flex; min-height: 70px; align-items: center; justify-content: flex-end; gap: 20px; color: #858e9d; font-size: 11px; }
.pagination button { min-width: 120px; height: 38px; border: 1px solid var(--aima-primary); border-radius: 6px; color: var(--aima-primary); background: #fff; cursor: pointer; }
.pagination button:disabled { border-color: #dfe3ea; color: #a4acba; cursor: default; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; padding: 11px 18px; border: 1px solid #a9e3c7; border-radius: 7px; color: #12804b; background: #effbf5; box-shadow: 0 8px 24px rgb(22 29 43 / 12%); transform: translateX(-50%); }
</style>
