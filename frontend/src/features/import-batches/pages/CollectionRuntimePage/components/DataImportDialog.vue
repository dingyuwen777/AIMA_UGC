<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type { DataImportIngestionPolicy } from '../../../../../generated/api/client'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import {
  type DataImportLocalFileSelection,
  useImportBatchesStore,
} from '../../../store'

type SourceKind = 'local_upload' | 'server_path'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'view-contents': [campaignId: string]
}>()
const store = useImportBatchesStore()
const sourceKind = ref<SourceKind>('local_upload')
const ingestionPolicy = ref<DataImportIngestionPolicy>('standard_observation')
const selectedLocalFiles = ref<DataImportLocalFileSelection[]>([])
const selectedPaths = ref<string[]>([])
const selectedPackIds = ref<string[]>([])
const validationError = ref<string | null>(null)
const notice = ref<string | null>(null)
const recursive = ref(false)
const maxFiles = 1_000
const maxBytes = 500 * 1024 * 1024
let pollHandle: ReturnType<typeof setInterval> | undefined
let pollInFlight = false
const activeStatuses = [
  'uploading',
  'discovering',
  'snapshotting',
  'queued',
  'running',
  'cancelling',
]

const currentPathLabel = computed(() => store.historicalDirectoryPath || '批准根目录')
const sourceSelectionReady = computed(() =>
  sourceKind.value === 'local_upload'
    ? selectedLocalFiles.value.length > 0
    : selectedPaths.value.length > 0,
)
const canCreate = computed(
  () =>
    !store.loadingHistorical &&
    !store.creatingHistorical &&
    sourceSelectionReady.value &&
    selectedPackIds.value.length > 0,
)
const canCancel = computed(() =>
  ['uploading', 'queued', 'running', 'cancelling'].includes(
    store.selectedHistoricalCampaign?.status ?? '',
  ),
)
const canRetry = computed(() =>
  ['partial_failed', 'failed'].includes(store.selectedHistoricalCampaign?.status ?? '') &&
  store.historicalCampaignItems.some(
    (item) => item.item_kind === 'chunk' && item.status === 'failed',
  ),
)
const canViewContents = computed(() => {
  const campaign = store.selectedHistoricalCampaign
  if (!campaign || !['succeeded', 'partial_failed'].includes(campaign.status)) return false
  const stats = campaign.stats
  return (
    (stats?.created ?? 0) +
    (stats?.filled ?? 0) +
    (stats?.updated ?? 0) +
    (stats?.unchanged ?? 0) +
    (stats?.conflict ?? 0)
  ) > 0
})
const preflightIndeterminate = computed(
  () => store.selectedHistoricalCampaign?.status === 'discovering',
)
const showImportProgress = computed(() => {
  const campaign = store.selectedHistoricalCampaign
  return Boolean(
    campaign &&
      campaign.total_rows > 0 &&
      !['uploading', 'discovering', 'snapshotting'].includes(campaign.status),
  )
})
const localUploadPercent = computed(() => {
  if (store.localUploadTotal <= 0) return 0
  return Math.floor(store.localUploadCompleted * 100 / store.localUploadTotal)
})

function stopPolling(): void {
  if (pollHandle !== undefined) clearInterval(pollHandle)
  pollHandle = undefined
}

async function pollCampaign(): Promise<void> {
  const campaign = store.selectedHistoricalCampaign
  if (
    !props.modelValue ||
    !campaign ||
    pollInFlight ||
    !activeStatuses.includes(campaign.status)
  ) return
  pollInFlight = true
  try {
    await store.refreshHistoricalCampaignSummary(campaign.id)
    if (!activeStatuses.includes(store.selectedHistoricalCampaign?.status ?? '')) {
      await store.refreshHistoricalCampaign(campaign.id)
    }
  } catch {
    notice.value = 'Campaign 状态刷新失败，页面会继续重试。'
  } finally {
    pollInFlight = false
  }
}

function startPolling(): void {
  stopPolling()
  pollHandle = setInterval(() => void pollCampaign(), 1_000)
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      startPolling()
      return
    }
    stopPolling()
    sourceKind.value = 'local_upload'
    ingestionPolicy.value = 'standard_observation'
    selectedLocalFiles.value = []
    selectedPaths.value = []
    selectedPackIds.value = []
    recursive.value = false
    validationError.value = null
    notice.value = null
  },
)

onBeforeUnmount(stopPolling)

async function chooseSource(value: SourceKind): Promise<void> {
  sourceKind.value = value
  ingestionPolicy.value = value === 'local_upload'
    ? 'standard_observation'
    : 'historical_fill_only'
  validationError.value = null
  if (value === 'server_path' && store.historicalDirectoryEntries.length === 0) {
    await store.openServerImportSource()
  }
}

function selectLocalFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  validationError.value = null
  const accepted: DataImportLocalFileSelection[] = []
  let ignored = 0
  for (const file of files) {
    const browserFile = file as File & { webkitRelativePath?: string }
    const relativePath = (browserFile.webkitRelativePath || file.name).replaceAll('\\', '/')
    if (!file.name.toLocaleLowerCase().endsWith('.xlsx')) {
      ignored += 1
      continue
    }
    if (file.size <= 0 || file.size > maxBytes) {
      validationError.value = `${relativePath} 必须大于 0 bytes 且不能超过 500 MiB。`
      return
    }
    const parts = relativePath.split('/')
    if (
      relativePath.startsWith('/') ||
      relativePath.includes(':') ||
      parts.some((part) => !part || part === '..')
    ) {
      validationError.value = '浏览器返回了不安全的相对路径，无法建立上传清单。'
      return
    }
    accepted.push({ file, relativePath })
  }
  if (accepted.length === 0) {
    validationError.value = ignored > 0
      ? '所选目录中没有 .xlsx 文件。'
      : '请至少选择一个 .xlsx 文件。'
    return
  }
  if (accepted.length > maxFiles) {
    validationError.value = `一次最多选择 ${maxFiles} 个 .xlsx 文件。`
    return
  }
  const paths = accepted.map((item) => item.relativePath)
  if (new Set(paths).size !== paths.length) {
    validationError.value = '所选文件包含重复相对路径。'
    return
  }
  selectedLocalFiles.value = accepted.sort((left, right) =>
    left.relativePath.localeCompare(right.relativePath),
  )
  if (ignored > 0) notice.value = `已忽略 ${ignored} 个非 .xlsx 文件。`
}

function parentPath(): string {
  const parts = store.historicalDirectoryPath.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
}

function togglePath(path: string): void {
  selectedPaths.value = selectedPaths.value.includes(path)
    ? selectedPaths.value.filter((item) => item !== path)
    : [...selectedPaths.value, path]
}

function togglePack(packId: string): void {
  selectedPackIds.value = selectedPackIds.value.includes(packId)
    ? selectedPackIds.value.filter((item) => item !== packId)
    : [...selectedPackIds.value, packId]
}

async function createCampaign(): Promise<void> {
  if (!canCreate.value) return
  validationError.value = null
  if (sourceKind.value === 'local_upload') {
    const campaign = await store.submitLocalCampaign(
      selectedLocalFiles.value,
      selectedPackIds.value,
      ingestionPolicy.value,
    )
    if (campaign) notice.value = '文件上传完成，服务器正在执行不可变快照与预检。'
    return
  }
  const created = await store.submitHistoricalCampaign({
    client_idempotency_key: crypto.randomUUID(),
    relative_paths: selectedPaths.value,
    keyword_pack_ids: selectedPackIds.value,
    recursive: recursive.value,
    profile: 'aima-monitoring-excel.v1',
    ingestion_policy: ingestionPolicy.value,
  })
  if (created) notice.value = 'Campaign 已创建，服务器正在完成不可变快照与预检。'
}

async function startCampaign(): Promise<void> {
  if (!store.selectedHistoricalCampaign?.can_start) return
  if (await store.actOnHistoricalCampaign('start')) notice.value = '导入任务已进入队列。'
}

async function cancelCampaign(): Promise<void> {
  if (await store.actOnHistoricalCampaign('cancel')) notice.value = '已请求取消 Campaign。'
}

async function retryCampaign(): Promise<void> {
  if (await store.actOnHistoricalCampaign('retry')) notice.value = '失败项已重新进入导入队列。'
}

function viewCampaignContents(): void {
  const campaignId = store.selectedHistoricalCampaign?.id
  if (!campaignId || !canViewContents.value) return
  emit('update:modelValue', false)
  emit('view-contents', campaignId)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="dialog-layer"
      role="presentation"
    >
      <section
        class="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="data-import-title"
      >
        <header>
          <div>
            <h2 id="data-import-title">
              导入数据
            </h2>
            <p>本机与服务器文件共用不可变 Artifact、预检、Chunk、进度和行账本。</p>
          </div>
          <button
            type="button"
            aria-label="关闭导入数据"
            :disabled="store.creatingHistorical"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header>

        <div class="dialog-body">
          <section
            class="source-tabs"
            aria-label="数据来源"
          >
            <button
              type="button"
              :class="{ selected: sourceKind === 'local_upload' }"
              :aria-pressed="sourceKind === 'local_upload'"
              :disabled="store.creatingHistorical"
              @click="chooseSource('local_upload')"
            >
              本地电脑
            </button>
            <button
              type="button"
              :class="{ selected: sourceKind === 'server_path' }"
              :aria-pressed="sourceKind === 'server_path'"
              :disabled="store.creatingHistorical"
              @click="chooseSource('server_path')"
            >
              服务器目录
            </button>
          </section>

          <section class="policy-panel">
            <strong>写入策略</strong>
            <label>
              <input
                v-model="ingestionPolicy"
                type="radio"
                value="standard_observation"
                :disabled="store.creatingHistorical"
              >
              <span><b>标准观测</b><small>沿用普通 Excel 导入：按观测时间更新 Current、Version 和可信 Metric。</small></span>
            </label>
            <label>
              <input
                v-model="ingestionPolicy"
                type="radio"
                value="historical_fill_only"
                :disabled="store.creatingHistorical"
              >
              <span><b>历史补空</b><small>只补 Current 空字段；已有非空冲突不覆盖，且无可信时间的 Metric 不更新。</small></span>
            </label>
            <p>来源与写入策略相互独立。AI 不会自动执行，需另行显式创建 Analysis Run。</p>
          </section>

          <section
            v-if="sourceKind === 'local_upload'"
            class="source-panel"
          >
            <div class="section-heading">
              <strong>本地文件</strong><span>已选 {{ selectedLocalFiles.length }} 个 .xlsx</span>
            </div>
            <p class="source-help">
              浏览器不会暴露本机绝对路径。可多选文件，或选择文件夹并自动遍历其中所有 .xlsx。
            </p>
            <div class="local-actions">
              <label>
                选择文件（可多选）
                <input
                  type="file"
                  accept=".xlsx"
                  multiple
                  :disabled="store.creatingHistorical"
                  @change="selectLocalFiles"
                >
              </label>
              <label>
                选择文件夹（自动遍历）
                <input
                  type="file"
                  accept=".xlsx"
                  multiple
                  webkitdirectory
                  directory
                  :disabled="store.creatingHistorical"
                  @change="selectLocalFiles"
                >
              </label>
            </div>
            <div
              v-if="selectedLocalFiles.length"
              class="local-file-list"
            >
              <span
                v-for="item in selectedLocalFiles.slice(0, 100)"
                :key="item.relativePath"
              >{{ item.relativePath }} <small>{{ item.file.size }} bytes</small></span>
              <small v-if="selectedLocalFiles.length > 100">仅预览前 100 个文件，清单会完整提交。</small>
            </div>
            <TaskProgressBar
              v-if="store.creatingHistorical && store.localUploadTotal > 0"
              label="本地文件上传进度"
              :value="localUploadPercent"
              :detail="`${store.localUploadCompleted} / ${store.localUploadTotal} 个文件已上传`"
            />
          </section>

          <section
            v-else
            class="source-panel"
          >
            <div class="section-heading">
              <strong>服务器目录</strong><span>{{ currentPathLabel }}</span>
            </div>
            <p class="source-help">
              只浏览管理员批准的只读根目录；HTTP 只传相对路径，不提供文件管理能力。
            </p>
            <button
              v-if="store.historicalDirectoryPath"
              class="directory-up"
              type="button"
              :disabled="store.loadingHistorical || store.creatingHistorical"
              @click="store.browseHistoricalDirectory(parentPath())"
            >
              ← 返回上级
            </button>
            <p
              v-if="store.loadingHistorical"
              class="empty-state"
            >
              正在读取批准目录…
            </p>
            <p
              v-else-if="store.historicalDirectoryEntries.length === 0"
              class="empty-state"
            >
              当前目录没有可选的 .xlsx 文件或子目录。
            </p>
            <div
              v-else
              class="directory-list"
            >
              <div
                v-for="entry in store.historicalDirectoryEntries"
                :key="entry.relative_path"
                class="directory-entry"
                :class="{ 'directory-entry--directory': entry.kind === 'directory' }"
              >
                <label>
                  <input
                    type="checkbox"
                    :aria-label="entry.kind === 'directory' ? `选择目录 ${entry.name}` : `选择 ${entry.name}`"
                    :checked="selectedPaths.includes(entry.relative_path)"
                    :disabled="store.creatingHistorical"
                    @change="togglePath(entry.relative_path)"
                  >
                  <span>{{ entry.kind === 'directory' ? '📁' : '📄' }} {{ entry.name }}<small>{{ entry.kind === 'directory' ? '选择此目录' : `${entry.byte_size ?? 0} bytes` }}</small></span>
                </label>
                <button
                  v-if="entry.kind === 'directory'"
                  type="button"
                  :aria-label="`打开目录 ${entry.name}`"
                  :disabled="store.creatingHistorical"
                  @click="store.browseHistoricalDirectory(entry.relative_path)"
                >
                  打开
                </button>
              </div>
            </div>
            <button
              v-if="store.historicalDirectoryHasMore"
              class="directory-more"
              type="button"
              :disabled="store.loadingHistorical || store.creatingHistorical"
              @click="store.loadMoreHistoricalDirectory()"
            >
              {{ store.loadingHistorical ? '正在加载…' : '加载更多目录项' }}
            </button>
            <label class="recursive-option">
              <input
                v-model="recursive"
                type="checkbox"
                :disabled="store.creatingHistorical"
              >
              选择目录时递归发现其中的 .xlsx（受服务器深度和文件数上限约束）
            </label>
          </section>

          <section class="pack-panel">
            <strong>关键词包（至少选择 1 个）</strong>
            <p
              v-if="store.loadingHistorical"
              class="empty-state"
            >
              正在读取关键词包…
            </p>
            <p
              v-else-if="store.keywordPackOptions.length === 0"
              class="empty-state"
            >
              当前没有可用的关键词包，请先在采集策略中创建并启用。
            </p>
            <div class="pack-list">
              <label
                v-for="pack in store.keywordPackOptions"
                :key="pack.id"
              >
                <input
                  type="checkbox"
                  :checked="selectedPackIds.includes(pack.id)"
                  :disabled="store.creatingHistorical"
                  @change="togglePack(pack.id)"
                >
                <span><b>{{ pack.name }}</b><small>{{ pack.keyword_count }} 个关键词 · v{{ pack.version }}</small></span>
              </label>
            </div>
          </section>

          <p
            v-if="validationError"
            class="error"
            role="alert"
          >
            {{ validationError }}
          </p>
          <button
            class="primary create-button"
            type="button"
            :disabled="!canCreate"
            :aria-busy="store.creatingHistorical"
            @click="createCampaign"
          >
            {{ store.creatingHistorical ? '正在创建…' : '创建并预检' }}
          </button>

          <section
            v-if="store.historicalCampaigns.length"
            class="campaign-history"
          >
            <strong>导入 Campaign</strong>
            <div>
              <button
                v-for="campaign in store.historicalCampaigns"
                :key="campaign.id"
                type="button"
                :aria-label="`打开 Campaign ${campaign.id}`"
                :class="{ selected: store.selectedHistoricalCampaign?.id === campaign.id }"
                @click="store.refreshHistoricalCampaign(campaign.id)"
              >
                <code>{{ campaign.id }}</code>
                <span>{{ campaign.source_kind === 'local_upload' ? '本机' : '服务器' }} · {{ campaign.status }}</span>
              </button>
            </div>
          </section>

          <section
            v-if="store.selectedHistoricalCampaign"
            class="campaign-panel"
          >
            <div class="section-heading">
              <strong>当前 Campaign</strong><code>{{ store.selectedHistoricalCampaign.id }}</code>
            </div>
            <p
              v-if="store.selectedHistoricalCampaign.status === 'ready'"
              class="ready-state"
            >
              预检完成，可开始导入
            </p>
            <p
              v-else
              class="status-state"
            >
              状态：{{ store.selectedHistoricalCampaign.status }}
            </p>
            <div class="campaign-facts">
              <span>来源 {{ store.selectedHistoricalCampaign.source_kind === 'local_upload' ? '本地电脑' : '服务器目录' }}</span>
              <span>策略 {{ store.selectedHistoricalCampaign.ingestion_policy === 'standard_observation' ? '标准观测' : '历史补空' }}</span>
              <span>文件 {{ store.selectedHistoricalCampaign.discovered_file_count }}</span>
              <span>已预检 {{ store.selectedHistoricalCampaign.ready_item_count }}</span>
              <span>行数 {{ store.selectedHistoricalCampaign.total_rows }}</span>
              <span>新建 {{ store.selectedHistoricalCampaign.stats?.created ?? 0 }}</span>
              <span>补空 {{ store.selectedHistoricalCampaign.stats?.filled ?? 0 }}</span>
              <span>更新 {{ store.selectedHistoricalCampaign.stats?.updated ?? 0 }}</span>
              <span>未变 {{ store.selectedHistoricalCampaign.stats?.unchanged ?? 0 }}</span>
              <span>冲突 {{ store.selectedHistoricalCampaign.stats?.conflict ?? 0 }}</span>
              <span>过滤 {{ store.selectedHistoricalCampaign.stats?.filtered ?? 0 }}</span>
              <span>重复 {{ store.selectedHistoricalCampaign.stats?.duplicate ?? 0 }}</span>
              <span>无效 {{ store.selectedHistoricalCampaign.stats?.invalid ?? 0 }}</span>
              <span>失败 {{ store.selectedHistoricalCampaign.stats?.failed ?? 0 }}</span>
            </div>
            <div class="campaign-progresses">
              <TaskProgressBar
                label="导入预检进度"
                :value="store.selectedHistoricalCampaign.progress.preflight_percent"
                :indeterminate="preflightIndeterminate"
                :detail="preflightIndeterminate
                  ? '正在枚举批准目录，文件总数尚未确定'
                  : `${store.selectedHistoricalCampaign.progress.preflight_completed_file_count} / ${store.selectedHistoricalCampaign.discovered_file_count} 个文件`"
              />
              <TaskProgressBar
                v-if="showImportProgress"
                label="数据导入进度"
                :value="store.selectedHistoricalCampaign.progress.migration_percent"
                :detail="`${store.selectedHistoricalCampaign.progress.migration_completed_row_count} / ${store.selectedHistoricalCampaign.total_rows} 行已取得终态`"
              />
            </div>
            <div
              v-if="store.historicalCampaignItems.length"
              class="campaign-items"
            >
              <div
                v-for="item in store.historicalCampaignItems"
                :key="item.id"
              >
                <span>{{ item.item_kind === 'source_file' ? '文件' : `Chunk ${item.ordinal}` }} · {{ item.relative_path }}</span>
                <b>{{ item.status }}</b><small v-if="item.error_code">{{ item.error_code }}</small>
              </div>
            </div>
            <small v-if="store.historicalCampaignItemsHasMore">明细按失败和运行状态优先，当前仅展示前 200 条。</small>
            <small v-if="store.historicalCampaignConflictsHasMore">冲突明细当前仅展示前 500 条；总数以 Campaign 统计为准。</small>
            <div class="campaign-actions">
              <button
                class="primary"
                type="button"
                :disabled="!store.selectedHistoricalCampaign.can_start || store.actingHistorical"
                @click="startCampaign"
              >
                开始导入
              </button>
              <button
                type="button"
                :disabled="!canCancel || store.actingHistorical"
                @click="cancelCampaign"
              >
                取消
              </button>
              <button
                type="button"
                :disabled="!canRetry || store.actingHistorical"
                @click="retryCampaign"
              >
                重试失败项
              </button>
              <button
                v-if="canViewContents"
                type="button"
                @click="viewCampaignContents"
              >
                查看导入内容
              </button>
            </div>
          </section>

          <p
            v-if="notice"
            class="notice"
            role="status"
          >
            {{ notice }}
          </p>
          <p
            v-if="store.error"
            class="error"
            role="alert"
          >
            {{ store.error }}
          </p>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-layer { position: fixed; z-index: 140; inset: 0; display: grid; place-items: center; background: rgb(22 29 43 / 48%); }
.dialog { width: min(840px, calc(100vw - 48px)); max-height: 90vh; overflow: hidden; border-radius: 11px; background: #fff; box-shadow: 0 22px 60px rgb(22 29 43 / 22%); }
header { display: flex; align-items: start; justify-content: space-between; padding: 19px 22px; border-bottom: 1px solid var(--aima-border); }
header h2 { margin: 0; font-size: 19px; }
header p { margin: 6px 0 0; color: #717b8d; font-size: 12px; }
header button { border: 0; color: #657087; background: transparent; cursor: pointer; font-size: 25px; }
.dialog-body { display: grid; gap: 16px; max-height: calc(90vh - 78px); padding: 20px 22px 24px; overflow: auto; }
.source-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.source-tabs button { height: 42px; border: 1px solid #d9dee7; border-radius: 7px; color: #596477; background: #fff; cursor: pointer; }
.source-tabs button.selected { border-color: var(--aima-primary); color: var(--aima-primary); background: #fff5f8; font-weight: 600; }
.policy-panel, .source-panel, .pack-panel, .campaign-panel, .campaign-history { padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; }
.policy-panel { display: grid; gap: 9px; }
.policy-panel label { display: flex; align-items: flex-start; gap: 9px; }
.policy-panel span { display: grid; gap: 3px; }
.policy-panel small, .policy-panel p, .source-help { margin: 0; color: #747f91; font-size: 12px; line-height: 1.6; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.section-heading span, .section-heading code { overflow: hidden; color: #7a8495; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.local-actions { display: flex; gap: 9px; margin-top: 12px; }
.local-actions label { padding: 9px 13px; border: 1px solid var(--aima-primary); border-radius: 6px; color: var(--aima-primary); cursor: pointer; font-size: 13px; }
.local-actions input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.local-file-list { display: grid; gap: 5px; max-height: 150px; margin-top: 10px; overflow: auto; padding: 9px; border-radius: 6px; background: #f7f8fa; font-size: 12px; }
.local-file-list span { display: flex; justify-content: space-between; gap: 12px; }
.local-file-list small { color: #8992a3; }
.directory-list, .pack-list { display: grid; gap: 7px; max-height: 220px; margin-top: 10px; overflow: auto; }
.directory-entry button, .directory-entry label, .pack-list label { display: flex; width: 100%; align-items: center; gap: 9px; padding: 9px 10px; border: 1px solid #e3e6ec; border-radius: 6px; color: #354052; background: #fff; text-align: left; cursor: pointer; }
.directory-entry--directory { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 7px; }
.directory-entry--directory button { width: auto; }
.directory-entry label span, .pack-list label span { display: flex; flex: 1; justify-content: space-between; gap: 10px; }
.directory-entry small, .pack-list small { color: #8a93a3; font-weight: normal; }
.directory-up { margin-top: 10px; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }
.directory-more { width: 100%; margin-top: 9px; padding: 8px; border: 1px solid #d9dee7; border-radius: 6px; color: #596477; background: #fff; cursor: pointer; }
.recursive-option { display: flex; align-items: center; gap: 8px; margin-top: 12px; color: #657087; font-size: 12px; }
.empty-state { color: #8992a3; font-size: 13px; }
.primary { border-color: var(--aima-primary) !important; color: #fff !important; background: var(--aima-primary) !important; }
.create-button { justify-self: end; height: 40px; padding: 0 20px; border: 1px solid; border-radius: 6px; cursor: pointer; }
.campaign-history > div { display: grid; gap: 6px; max-height: 128px; margin-top: 9px; overflow: auto; }
.campaign-history button { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 10px; border: 1px solid #e3e6ec; border-radius: 6px; color: #596477; background: #fff; cursor: pointer; }
.campaign-history button.selected { border-color: var(--aima-primary); background: #f1f7ff; }
.campaign-history code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.campaign-facts { display: flex; flex-wrap: wrap; gap: 8px; }
.campaign-facts span { padding: 5px 8px; border-radius: 5px; color: #596477; background: #f3f5f8; font-size: 12px; }
.campaign-progresses { display: grid; gap: 12px; margin-top: 14px; }
.campaign-actions { display: flex; gap: 8px; margin-top: 13px; }
.campaign-actions button { height: 36px; padding: 0 14px; border: 1px solid #d9dee7; border-radius: 6px; background: #fff; cursor: pointer; }
.campaign-items { display: grid; gap: 6px; max-height: 150px; margin-top: 12px; overflow: auto; }
.campaign-items > div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 10px; padding: 7px 9px; border-radius: 5px; background: #f7f8fa; font-size: 11px; }
.campaign-items span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.campaign-items small { grid-column: 1 / -1; color: var(--aima-danger); }
.ready-state, .notice { color: #087747; }
.status-state { color: #596477; }
.notice, .error { margin: 0; font-size: 13px; }
.error { color: var(--aima-danger); }
button:disabled { cursor: not-allowed; opacity: .55; }
</style>
