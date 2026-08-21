<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type {
  CollectionRunCreateRequest,
  CollectionRuntimeItemResponse,
} from '../../../../generated/api/client'
import AppShell from '../../../../app/layouts/AppShell.vue'
import { useImportBatchesStore } from '../../store'
import CollectionRunDetailDrawer from './components/CollectionRunDetailDrawer.vue'
import CollectionRuntimeFilters from './components/CollectionRuntimeFilters.vue'
import CollectionRuntimeKpiCards from './components/CollectionRuntimeKpiCards.vue'
import CollectionRuntimeTable from './components/CollectionRuntimeTable.vue'
import ImportBatchDetailDrawer from './components/ImportBatchDetailDrawer.vue'
import ImportUploadDialog from './components/ImportUploadDialog.vue'
import TikHubSupplementDrawer from './components/TikHubSupplementDrawer.vue'

const store = useImportBatchesStore()
const router = useRouter()
const uploadOpen = ref(false)
const supplementOpen = ref(false)
const initialBatchId = ref<string | null>(null)
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
  store.startPolling(5000)
})

onBeforeUnmount(() => store.stopPolling())

async function search(): Promise<void> {
  await store.refresh()
}

async function reset(): Promise<void> {
  store.resetFilters()
  await store.refresh()
}

async function upload(file: File): Promise<void> {
  const created = await store.upload(file)
  if (!created) return
  uploadOpen.value = false
  showNotice('Import Job 已创建，文件将在后台继续处理。')
  await store.openBatchDetail(created.batch_id)
}

async function openCreate(batchId: string | null = null): Promise<void> {
  initialBatchId.value = batchId
  await store.loadCreationOptions(batchId)
  supplementOpen.value = true
}

async function createRun(request: CollectionRunCreateRequest): Promise<void> {
  const created = await store.createRun(request)
  if (!created) return
  supplementOpen.value = false
  showNotice('TikHub Collection Run / Job 已创建，将由 Worker 在后台执行。')
}

async function selectItem(item: CollectionRuntimeItemResponse): Promise<void> {
  if (item.record_type === 'excel_import') {
    await store.openBatchDetail(item.import_batch_id ?? item.record_id)
    return
  }
  await store.openRunDetail(item.collection_run_id ?? item.record_id)
}

async function copy(value: string): Promise<void> {
  try {
    if (!navigator.clipboard) throw new Error('Clipboard API unavailable')
    await navigator.clipboard.writeText(value)
    showNotice('ID 已复制。')
  } catch {
    showNotice('复制失败，请检查浏览器剪贴板权限。')
  }
}

function showNotice(message: string): void {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) notice.value = null
  }, 2600)
}

async function viewContents(batchId: string): Promise<void> {
  await router.push({ name: 'voice-plaza', query: { source_identifier: batchId } })
}
</script>

<template>
  <AppShell>
    <div class="page-header">
      <div><h1>采集运行中心</h1><p>统一查看 Excel 导入与 TikHub 辅助补采运行</p></div>
      <div class="page-actions">
        <button
          type="button"
          @click="store.refresh()"
        >
          ↻&nbsp; 刷新数据
        </button><button
          class="primary"
          type="button"
          @click="uploadOpen = true"
        >
          ⇧&nbsp; 导入 Excel
        </button><button
          class="outline-primary"
          type="button"
          @click="openCreate()"
        >
          ＋&nbsp; 新建 TikHub 补采
        </button>
      </div>
    </div>

    <CollectionRuntimeKpiCards
      :summary="store.summary"
      :loading="store.loading"
    />
    <nav
      class="runtime-tabs"
      aria-label="运行类型"
    >
      <button
        v-for="tab in [{ value: 'all', label: '全部运行' }, { value: 'excel', label: 'Excel 导入' }, { value: 'tikhub', label: 'TikHub 辅助补采' }] as const"
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
      v-model:stage="store.filters.stage"
      v-model:created-from="store.filters.createdFrom"
      v-model:created-to="store.filters.createdTo"
      :active-tab="store.activeTab"
      @search="search"
      @reset="reset"
    />
    <div
      v-if="store.error"
      class="page-error"
      role="alert"
    >
      !&nbsp; {{ store.error }}
    </div>

    <div class="list-heading">
      <strong>采集运行记录</strong><span>创建时间：最新优先</span>
    </div>
    <CollectionRuntimeTable
      :items="store.items"
      :loading="store.loading"
      @select="selectItem"
      @supplement="openCreate"
    />
    <div class="pagination">
      <span>已加载 {{ store.items.length }} 条</span><button
        type="button"
        :disabled="!store.hasMore || store.loadingNext"
        @click="store.loadNext()"
      >
        {{ store.loadingNext ? '加载中…' : store.hasMore ? '下一页 →' : '已加载全部' }}
      </button>
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
    <ImportUploadDialog
      v-model="uploadOpen"
      :uploading="store.uploading"
      @submit="upload"
    />
    <TikHubSupplementDrawer
      v-model="supplementOpen"
      :capabilities="store.capabilities"
      :batches="store.batchOptions"
      :creating="store.creating"
      :initial-batch-id="initialBatchId"
      @submit="createRun"
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
.page-actions button { height: 42px; padding: 0 16px; border: 1px solid #d7dce5; border-radius: 7px; color: #384153; background: #fff; cursor: pointer; }
.page-actions .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); box-shadow: 0 5px 14px rgb(245 0 87 / 18%); }
.page-actions .outline-primary { border-color: var(--aima-primary); color: var(--aima-primary); }
.runtime-tabs { display: flex; gap: 10px; margin-bottom: 14px; border-bottom: 1px solid var(--aima-border); }
.runtime-tabs button { height: 45px; padding: 0 14px; border: 0; border-bottom: 2px solid transparent; color: #566174; background: transparent; cursor: pointer; }
.runtime-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.page-error { margin-top: 15px; padding: 12px 14px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 13px; }
.list-heading { display: flex; align-items: center; justify-content: space-between; margin: 22px 0 12px; }
.list-heading strong { font-size: 17px; }
.list-heading span { padding: 9px 13px; border: 1px solid #dfe3ea; border-radius: 6px; color: #5f6879; background: #fff; font-size: 12px; }
.pagination { display: flex; min-height: 70px; align-items: center; justify-content: flex-end; gap: 20px; color: #717b8d; font-size: 13px; }
.pagination button { min-width: 120px; height: 40px; border: 1px solid var(--aima-primary); border-radius: 7px; color: var(--aima-primary); background: #fff; cursor: pointer; }
.pagination button:disabled { border-color: #dfe3ea; color: #a4acba; cursor: default; }
.notice { position: fixed; z-index: 200; top: 76px; left: 50%; padding: 11px 18px; border: 1px solid #a9e3c7; border-radius: 7px; color: #12804b; background: #effbf5; box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
</style>
