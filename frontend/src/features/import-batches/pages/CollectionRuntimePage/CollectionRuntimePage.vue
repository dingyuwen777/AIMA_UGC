<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type {
  CollectionRunCreateRequest,
  CollectionRuntimeItemResponse,
} from '../../../../generated/api/client'
import AppShell from '../../../../app/layouts/AppShell.vue'
import AimaButton from '../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../../shared/ui/AimaPageHeader.vue'
import {
  type SupplementSourceSelection,
  useImportBatchesStore,
} from '../../store'
import CollectionRunDetailDrawer from './components/CollectionRunDetailDrawer.vue'
import CollectionRuntimeFilters from './components/CollectionRuntimeFilters.vue'
import CollectionRuntimeKpiCards from './components/CollectionRuntimeKpiCards.vue'
import CollectionRuntimeTable from './components/CollectionRuntimeTable.vue'
import DataImportDialog from './components/DataImportDialog.vue'
import ImportBatchDetailDrawer from './components/ImportBatchDetailDrawer.vue'
import TikHubSupplementDrawer from './components/TikHubSupplementDrawer.vue'

const store = useImportBatchesStore()
const route = useRoute()
const router = useRouter()
const dataImportOpen = ref(false)
const supplementOpen = ref(false)
const initialSupplementSource = ref<SupplementSourceSelection | null>(null)
const notice = ref<string | null>(null)
const batchDetailOpen = computed({
  get: () => store.selectedBatch !== null,
  set: (open: boolean) => {
    if (!open) store.closeDetail()
  },
})
const runDetailOpen = computed({
  get: () => store.selectedRun !== null,
  set: (open: boolean) => {
    if (!open) store.closeDetail()
  },
})

onMounted(async () => {
  await store.refresh()
  await openCampaignFromRoute()
  store.startPolling(5000)
})

onBeforeUnmount(() => store.stopPolling())

/** 处理任务中心的失败导入深链；无效链接只提示，不阻塞运行中心普通使用。 */
async function openCampaignFromRoute(): Promise<void> {
  const campaignId = route.query.data_import_campaign_id
  if (typeof campaignId !== 'string' || !campaignId) return
  store.selectedHistoricalCampaign = null
  dataImportOpen.value = true
  await store.openHistoricalWorkspace()
  try {
    await store.refreshHistoricalCampaign(campaignId)
  } catch {
    showNotice('指定导入任务暂不可打开，请从列表重新选择。')
  }
}

/** 使用当前筛选值刷新第一页，并由 Store 冻结为后续 Cursor Window 的查询条件。 */
async function search(): Promise<void> {
  await store.refresh()
}

/** 恢复产品默认筛选后立即刷新，避免界面值和列表结果不同步。 */
async function reset(): Promise<void> {
  store.resetFilters()
  await store.refresh()
}

/** 打开统一数据导入工作区，创建状态不预选历史 Campaign。 */
async function openDataImport(): Promise<void> {
  store.selectedHistoricalCampaign = null
  dataImportOpen.value = true
  await store.openHistoricalWorkspace()
}

/** 打开辅助补采；从列表发起时可把当前导入来源作为初始补采来源。 */
async function openCreate(source: SupplementSourceSelection | null = null): Promise<void> {
  initialSupplementSource.value = source
  await store.loadCreationOptions(source)
  supplementOpen.value = true
}

/** 创建成功后关闭表单并使用产品可读反馈，后台执行继续由 Store 轮询。 */
async function createRun(request: CollectionRunCreateRequest): Promise<void> {
  const created = await store.createRun(request)
  if (!created) return
  supplementOpen.value = false
  showNotice('辅助补采任务已创建，将在后台执行。')
}

/** 根据统一运行记录的真实 record_type 进入对应详情 Owner。 */
async function selectItem(item: CollectionRuntimeItemResponse): Promise<void> {
  if (item.record_type === 'excel_import') {
    await store.openBatchDetail(item.import_batch_id ?? item.record_id)
    return
  }
  if (item.record_type === 'data_import_campaign') {
    store.selectedHistoricalCampaign = null
    dataImportOpen.value = true
    await store.openHistoricalWorkspace()
    await store.refreshHistoricalCampaign(item.data_import_campaign_id ?? item.record_id)
    return
  }
  await store.openRunDetail(item.collection_run_id ?? item.record_id)
}

/** 技术详情中的标识复制失败只反馈权限问题，不影响任务本身。 */
async function copy(value: string): Promise<void> {
  try {
    if (!navigator.clipboard) throw new Error('Clipboard API unavailable')
    await navigator.clipboard.writeText(value)
    showNotice('ID 已复制。')
  } catch {
    showNotice('复制失败，请检查浏览器剪贴板权限。')
  }
}

/** 页面 Toast 使用单一短时状态，后来的消息不会被旧定时器提前清除。 */
function showNotice(message: string): void {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) notice.value = null
  }, 2600)
}

/** 从导入详情跳到声音广场时继续使用真实来源标识筛选。 */
async function viewContents(batchId: string): Promise<void> {
  await router.push({ name: 'voice-plaza', query: { source_identifier: batchId } })
}
</script>

<template>
  <AppShell>
    <AimaPageHeader
      class="runtime-page-header"
      title="采集运行中心"
      description="统一查看数据导入与辅助补采运行"
    >
      <template #actions>
        <AimaButton
          class="runtime-action runtime-action--refresh"
          variant="secondary"
          @click="store.refresh()"
        >
          刷新数据
        </AimaButton>
        <AimaButton
          class="runtime-action runtime-action--import"
          variant="secondary"
          @click="openDataImport"
        >
          导入数据
        </AimaButton>
        <AimaButton
          class="runtime-action runtime-action--create"
          variant="primary"
          @click="openCreate()"
        >
          新建辅助补采
        </AimaButton>
      </template>
    </AimaPageHeader>

    <CollectionRuntimeKpiCards
      :summary="store.summary"
      :loading="store.loading"
    />
    <nav
      class="runtime-tabs"
      aria-label="运行类型"
    >
      <button
        v-for="tab in [{ value: 'all', label: '全部运行' }, { value: 'excel', label: '数据导入' }, { value: 'tikhub', label: '辅助补采' }] as const"
        :key="tab.value"
        type="button"
        :class="{ active: store.activeTab === tab.value }"
        @click="store.setTab(tab.value)"
      >
        {{ tab.label }}
      </button>
    </nav>
    <CollectionRuntimeFilters
      v-model:search="store.filters.search"
      v-model:status="store.filters.status"
      v-model:record-type="store.filters.recordType"
      v-model:created-from="store.filters.createdFrom"
      v-model:created-to="store.filters.createdTo"
      :active-tab="store.activeTab"
      @search="search"
      @reset="reset"
    />
    <AimaFeedbackBanner
      v-if="store.error && store.items.length > 0"
      class="page-error"
      tone="error"
      role="alert"
    >
      采集运行刷新失败，当前列表已保留，请稍后重试。
    </AimaFeedbackBanner>

    <div class="list-heading">
      <strong>采集运行记录</strong>
    </div>
    <CollectionRuntimeTable
      :items="store.items"
      :loading="store.loading"
      :error="store.error"
      @select="selectItem"
      @supplement="openCreate"
      @retry="store.refresh()"
    />
    <div class="pagination">
      <span>已加载 {{ store.items.length }} 条</span>
      <AimaButton
        variant="secondary"
        size="small"
        :disabled="!store.hasMore || store.loadingNext"
        @click="store.loadNext()"
      >
        {{ store.loadingNext ? '加载中…' : store.hasMore ? '下一页' : '已加载全部' }}
      </AimaButton>
    </div>

    <ImportBatchDetailDrawer
      v-model="batchDetailOpen"
      :item="store.selectedBatch"
      @refresh="store.selectedBatch && store.openBatchDetail(store.selectedBatch.id)"
      @copy="copy"
      @view-contents="viewContents"
    />
    <CollectionRunDetailDrawer
      v-model="runDetailOpen"
      :item="store.selectedRun"
      @refresh="store.selectedRun && store.openRunDetail(store.selectedRun.run_id)"
      @copy="copy"
    />
    <DataImportDialog
      v-model="dataImportOpen"
      @view-contents="viewContents"
    />
    <TikHubSupplementDrawer
      v-model="supplementOpen"
      :capabilities="store.capabilities"
      :campaigns="store.campaignOptions"
      :batches="store.batchOptions"
      :keyword-packs="store.keywordPackOptions"
      :supplement-content-platforms="store.supplementContentPlatforms"
      :loading-supplement-platforms="store.loadingSupplementPlatforms"
      :creating="store.creating"
      :initial-source="initialSupplementSource"
      @source-change="store.loadSupplementPlatforms"
      @submit="createRun"
    />
    <div
      v-if="notice"
      class="notice"
      role="status"
    >
      <AimaFeedbackBanner tone="success">
        {{ notice }}
      </AimaFeedbackBanner>
    </div>
  </AppShell>
</template>

<style scoped>
.runtime-tabs { display: flex; gap: 8px; min-height: 40px; margin-top: 24px; margin-bottom: 20px; border-bottom: 0; }
.runtime-tabs button { min-height: 40px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; line-height: 20px; }
.runtime-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.page-error { margin-top: 16px; }
.list-heading { display: flex; min-height: 24px; align-items: center; margin: 34px 0 12px; }
.list-heading strong { color: var(--aima-text); font-size: 16px; font-weight: 500; line-height: 24px; }
.pagination { display: flex; min-height: 40px; align-items: center; justify-content: space-between; gap: 20px; margin-top: 24px; color: var(--aima-text-disabled); font-size: 12px; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; width: min(560px, calc(100vw - 48px)); transform: translateX(-50%); }
.runtime-page-header :deep(h1) { font-size: 24px; font-weight: 700; line-height: 32px; }
.runtime-page-header :deep(p) { margin-top: 6px; font-size: 12px; line-height: 18px; }
.runtime-page-header :deep(.aima-page-actions) { gap: 12px; }
.runtime-action--refresh,
.runtime-action--import { min-width: 104px; }
.runtime-action--create { min-width: 150px; }
@media (min-width: 981px) {
  .runtime-page-header { margin-top: 4px; flex-wrap: nowrap; align-items: center; }
  .runtime-page-header :deep(.aima-page-actions) { flex: none; justify-content: flex-end; }
}
@media (max-width: 980px) {
  .runtime-page-header :deep(.aima-page-actions) { width: 100%; justify-content: flex-start; }
}
</style>
