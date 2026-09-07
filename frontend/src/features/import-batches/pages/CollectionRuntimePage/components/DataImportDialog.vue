<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type {
  DataImportIngestionPolicy,
  HistoricalCampaignItemStatus,
  HistoricalCampaignResponse,
  HistoricalCampaignStatus,
} from '../../../../../generated/api/client'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import { createClientIdempotencyKey } from '../../../../../shared/idempotency'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { formatDateTime } from '../../../format'
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
const selectedVehicleIds = ref<string[]>([])
const validationError = ref<string | null>(null)
const notice = ref<string | null>(null)
const revocationReason = ref('')
const recursive = ref(false)
const maxFiles = 1_000
const maxBytes = 500 * 1024 * 1024
const campaignPollIntervalMs = 5_000
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

const historicalCampaignStatusLabels: Record<HistoricalCampaignStatus, string> = {
  uploading: '正在上传文件',
  discovering: '正在确认数据来源',
  snapshotting: '正在准备导入',
  ready: '预检完成',
  queued: '等待导入',
  running: '正在导入',
  cancelling: '正在取消',
  cancelled: '已取消',
  succeeded: '导入完成',
  partial_failed: '部分导入失败',
  failed: '导入失败',
}

const historicalItemStatusLabels: Record<HistoricalCampaignItemStatus, string> = {
  discovered: '已发现',
  snapshotting: '准备中',
  ready: '等待导入',
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

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
    (selectedPackIds.value.length > 0 || selectedVehicleIds.value.length > 0),
)
const canCancel = computed(() =>
  ['uploading', 'queued', 'running', 'cancelling'].includes(
    store.selectedHistoricalCampaign?.status ?? '',
  ),
)
const canRetry = computed(() =>
  ['partial_failed', 'failed'].includes(store.selectedHistoricalCampaign?.status ?? '') &&
  (store.selectedHistoricalCampaign?.failed_chunk_count ?? 0) > 0,
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
const canPreviewRevocation = computed(() =>
  ['succeeded', 'partial_failed'].includes(store.selectedHistoricalCampaign?.status ?? ''),
)
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
const revocationUnavailableMessage = computed(() => {
  const reason = store.historicalRevocationPreview?.ineligible_reason
  if (reason === 'campaign_not_completed') return '导入尚未完成，当前不能撤销。'
  if (reason === 'reversible_evidence_missing') {
    return '缺少足够的可逆来源证据，系统已阻止自动撤销，避免误删其它来源仍需要的数据。'
  }
  return '当前导入不满足安全撤销条件。'
})

function campaignDisplayName(campaign: HistoricalCampaignResponse): string {
  const path = campaign.root_relative_path.replaceAll('\\', '/').replace(/\/$/, '')
  const leaf = path.split('/').filter(Boolean).at(-1)
  if (leaf) return leaf
  return campaign.source_kind === 'local_upload' ? '本地文件导入' : '服务器目录导入'
}

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
    notice.value = '导入任务状态刷新失败，页面会继续重试。'
  } finally {
    pollInFlight = false
  }
}

/** 按页面统一的约 5 秒节奏启动导入任务状态轮询。 */
function startPolling(): void {
  stopPolling()
  pollHandle = setInterval(() => void pollCampaign(), campaignPollIntervalMs)
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
    selectedVehicleIds.value = []
    revocationReason.value = ''
    recursive.value = false
    validationError.value = null
    notice.value = null
  },
)

onBeforeUnmount(stopPolling)

async function chooseSource(value: SourceKind): Promise<void> {
  sourceKind.value = value
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
      selectedVehicleIds.value,
      ingestionPolicy.value,
    )
    if (campaign) notice.value = '文件上传完成，服务器正在准备并预检数据。'
    return
  }
  const created = await store.submitHistoricalCampaign({
    client_idempotency_key: createClientIdempotencyKey(),
    relative_paths: selectedPaths.value,
    keyword_pack_ids: selectedPackIds.value,
    vehicle_model_ids: selectedVehicleIds.value,
    recursive: recursive.value,
    profile: 'aima-monitoring-excel.v1',
    ingestion_policy: ingestionPolicy.value,
  })
  if (created) notice.value = '导入任务已创建，服务器正在准备并预检数据。'
}

async function startCampaign(): Promise<void> {
  if (!store.selectedHistoricalCampaign?.can_start) return
  if (await store.actOnHistoricalCampaign('start')) notice.value = '导入任务已进入处理队列。'
}

async function cancelCampaign(): Promise<void> {
  if (!await store.actOnHistoricalCampaign('cancel')) return
  notice.value = '已请求取消导入任务。'
  await pollCampaign()
}

async function retryCampaign(): Promise<void> {
  if (await store.actOnHistoricalCampaign('retry')) notice.value = '失败数据已重新进入处理队列。'
}

async function previewRevocation(): Promise<void> {
  const preview = await store.previewHistoricalRevocation()
  if (preview?.already_revoked) notice.value = '这次导入已经撤销，无需重复操作。'
}

async function revokeImport(): Promise<void> {
  const preview = store.historicalRevocationPreview
  if (!preview?.eligible || preview.already_revoked) return
  const { affected_content_count: affected, hidden_content_count: hidden, retained_shared_content_count: retained } = preview.impact
  if (!window.confirm(
    `确认撤销这次导入吗？将重新计算 ${affected} 条受影响内容，其中 ${hidden} 条会从当前业务视图隐藏，${retained} 条因仍有其他来源会继续保留。导入记录和审计证据不会删除。`,
  )) return
  const result = await store.revokeHistoricalImport(revocationReason.value)
  if (!result) return
  notice.value = result.already_revoked
    ? '这次导入此前已经撤销。'
    : `撤销完成：影响 ${result.impact.affected_content_count} 条内容，共享来源仍保留 ${result.impact.retained_shared_content_count} 条。`
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
            <p>从本地电脑或服务器批准目录创建导入任务，并按词包与车型规则完成预检；预检通过后再确认开始入库。</p>
          </div>
          <AimaButton
            variant="text"
            size="small"
            aria-label="关闭导入数据"
            :disabled="store.creatingHistorical"
            @click="emit('update:modelValue', false)"
          >
            关闭
          </AimaButton>
        </header>

        <div class="dialog-body">
          <section
            v-if="store.historicalCampaigns.length && !store.selectedHistoricalCampaign"
            class="campaign-history"
          >
            <strong>导入任务</strong>
            <div>
              <button
                v-for="campaign in store.historicalCampaigns"
                :key="campaign.id"
                type="button"
                :aria-label="`打开导入任务 ${campaignDisplayName(campaign)}`"
                @click="store.refreshHistoricalCampaign(campaign.id)"
              >
                <span class="campaign-name"><b>{{ campaignDisplayName(campaign) }}</b><small>{{ formatDateTime(campaign.created_at) }}</small></span>
                <span>{{ campaign.source_kind === 'local_upload' ? '本地电脑' : '服务器目录' }} · {{ historicalCampaignStatusLabels[campaign.status] }}</span>
              </button>
            </div>
          </section>

          <template v-if="!store.selectedHistoricalCampaign">
            <nav
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
            </nav>

            <section class="policy-panel">
              <strong>写入策略</strong>
              <div class="policy-grid">
                <label :class="{ selected: ingestionPolicy === 'standard_observation' }">
                  <input
                    v-model="ingestionPolicy"
                    type="radio"
                    value="standard_observation"
                    :disabled="store.creatingHistorical"
                  >
                  <span><b>标准观测</b><small>按当前观测语义写入或更新内容事实</small></span>
                </label>
                <label :class="{ selected: ingestionPolicy === 'historical_fill_only' }">
                  <input
                    v-model="ingestionPolicy"
                    type="radio"
                    value="historical_fill_only"
                    :disabled="store.creatingHistorical"
                  >
                  <span><b>历史补空</b><small>只补充历史缺失字段，不覆盖已有观测事实</small></span>
                </label>
              </div>
            </section>

            <section
              v-if="sourceKind === 'local_upload'"
              class="source-panel"
            >
              <div class="section-heading">
                <strong>本地数据文件</strong><span>已选 {{ selectedLocalFiles.length }} 个 .xlsx</span>
              </div>
              <p class="source-help">
                支持多选 .xlsx 文件或选择文件夹自动遍历；单文件最大 500 MiB，总文件数上限 1000。
              </p>
              <div class="local-actions">
                <label>
                  选择文件
                  <input
                    type="file"
                    accept=".xlsx"
                    multiple
                    :disabled="store.creatingHistorical"
                    @change="selectLocalFiles"
                  >
                </label>
                <label class="folder-action">
                  选择文件夹
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
                <strong>服务器批准目录</strong><span>当前：{{ currentPathLabel }}</span>
                <AimaButton
                  v-if="store.historicalDirectoryPath"
                  variant="text"
                  size="small"
                  :disabled="store.loadingHistorical || store.creatingHistorical"
                  @click="store.browseHistoricalDirectory(parentPath())"
                >
                  上一级
                </AimaButton>
              </div>
              <p class="source-help">
                只浏览管理员批准的只读根目录；页面只选择数据来源，不提供服务器文件管理能力。
              </p>
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
                    <span><b>{{ entry.name }}</b><small>{{ entry.kind === 'directory' ? '目录 · 选择此目录' : `${entry.byte_size ?? 0} bytes` }}</small></span>
                  </label>
                  <AimaButton
                    v-if="entry.kind === 'directory'"
                    variant="text"
                    size="small"
                    :aria-label="`打开目录 ${entry.name}`"
                    :disabled="store.creatingHistorical"
                    @click="store.browseHistoricalDirectory(entry.relative_path)"
                  >
                    打开
                  </AimaButton>
                </div>
              </div>
              <AimaButton
                v-if="store.historicalDirectoryHasMore"
                class="directory-more"
                variant="secondary"
                size="small"
                :disabled="store.loadingHistorical || store.creatingHistorical"
                @click="store.loadMoreHistoricalDirectory()"
              >
                {{ store.loadingHistorical ? '正在加载…' : '加载更多目录项' }}
              </AimaButton>
              <label class="recursive-option">
                <input
                  v-model="recursive"
                  type="checkbox"
                  :disabled="store.creatingHistorical"
                >
                选择目录时递归发现其中的 .xlsx
                <small>受服务器深度、文件数、批准根目录和分页限制</small>
              </label>
            </section>

            <section class="pack-panel">
              <strong>关键词包（与车型至少选择一项）</strong>
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
              <small class="pack-help">选项只展示当前已启用且可用的词包</small>
            </section>

            <VehicleMultiSelect
              v-model="selectedVehicleIds"
              label="车型（与词包统一筛选，可多选）"
              :disabled="store.creatingHistorical"
            />

            <AimaFeedbackBanner tone="info">
              创建后先完成来源确认、数据快照与预检；AI 不会自动执行，智能分析需要在分析入口手动创建。
            </AimaFeedbackBanner>
          </template>

          <template v-else>
            <section
              v-if="store.historicalCampaigns.length"
              class="campaign-history"
            >
              <strong>导入任务</strong>
              <div>
                <button
                  v-for="campaign in store.historicalCampaigns"
                  :key="campaign.id"
                  type="button"
                  :aria-label="`打开导入任务 ${campaignDisplayName(campaign)}`"
                  :class="{ selected: store.selectedHistoricalCampaign?.id === campaign.id }"
                  @click="store.refreshHistoricalCampaign(campaign.id)"
                >
                  <span class="campaign-name"><b>{{ campaignDisplayName(campaign) }}</b><small>{{ formatDateTime(campaign.created_at) }}</small></span>
                  <span>{{ historicalCampaignStatusLabels[campaign.status] }}</span>
                </button>
              </div>
            </section>

            <section class="campaign-panel">
              <div class="section-heading">
                <strong>{{ campaignDisplayName(store.selectedHistoricalCampaign) }}</strong><span>{{ formatDateTime(store.selectedHistoricalCampaign.created_at) }}</span>
              </div>
              <div
                class="campaign-status"
                :class="`campaign-status--${store.selectedHistoricalCampaign.status}`"
              >
                {{ historicalCampaignStatusLabels[store.selectedHistoricalCampaign.status] }}
              </div>
              <div class="campaign-facts">
                <span>来源<b>{{ store.selectedHistoricalCampaign.source_kind === 'local_upload' ? '本地电脑' : '服务器目录' }}</b></span>
                <span>策略<b>{{ store.selectedHistoricalCampaign.ingestion_policy === 'standard_observation' ? '标准观测' : '历史补空' }}</b></span>
                <span>文件<b>{{ store.selectedHistoricalCampaign.discovered_file_count }}</b></span>
                <span>已预检<b>{{ store.selectedHistoricalCampaign.ready_item_count }}</b></span>
                <span>行数<b>{{ store.selectedHistoricalCampaign.total_rows }}</b></span>
              </div>
              <div class="campaign-progresses">
                <TaskProgressBar
                  label="导入预检进度"
                  :value="store.selectedHistoricalCampaign.progress.preflight_percent"
                  :indeterminate="preflightIndeterminate"
                  :detail="preflightIndeterminate
                    ? '正在枚举批准目录，文件总数尚未确定'
                    : `${store.selectedHistoricalCampaign.progress.preflight_completed_file_count} / ${store.selectedHistoricalCampaign.discovered_file_count} 个文件已完成预检`"
                />
                <TaskProgressBar
                  v-if="showImportProgress"
                  label="数据导入进度"
                  :value="store.selectedHistoricalCampaign.progress.migration_percent"
                  :detail="`${store.selectedHistoricalCampaign.progress.migration_completed_row_count} / ${store.selectedHistoricalCampaign.total_rows} 行已处理`"
                />
              </div>
              <AimaFeedbackBanner
                v-if="store.selectedHistoricalCampaign.error_summary"
                tone="error"
                role="alert"
              >
                {{ store.selectedHistoricalCampaign.error_summary }}
              </AimaFeedbackBanner>
              <AimaFeedbackBanner tone="info">
                预检只准备导入任务；AI 不会自动执行，智能分析仍需在分析入口显式创建。
              </AimaFeedbackBanner>
            </section>

            <section class="campaign-stats">
              <strong>处理统计</strong>
              <div>
                <span>新建 <b>{{ store.selectedHistoricalCampaign.stats?.created ?? 0 }}</b></span>
                <span>补空 <b>{{ store.selectedHistoricalCampaign.stats?.filled ?? 0 }}</b></span>
                <span>更新 <b>{{ store.selectedHistoricalCampaign.stats?.updated ?? 0 }}</b></span>
                <span>未变 <b>{{ store.selectedHistoricalCampaign.stats?.unchanged ?? 0 }}</b></span>
                <span>冲突 <b>{{ store.selectedHistoricalCampaign.stats?.conflict ?? 0 }}</b></span>
                <span>过滤 <b>{{ store.selectedHistoricalCampaign.stats?.filtered ?? 0 }}</b></span>
                <span>重复 <b>{{ store.selectedHistoricalCampaign.stats?.duplicate ?? 0 }}</b></span>
                <span>无效 <b>{{ store.selectedHistoricalCampaign.stats?.invalid ?? 0 }}</b></span>
                <span>失败 <b>{{ store.selectedHistoricalCampaign.stats?.failed ?? 0 }}</b></span>
              </div>
            </section>

            <section
              v-if="store.historicalRevocationPreview"
              class="revocation-panel"
            >
              <div class="section-heading">
                <strong>撤销影响</strong><span>{{ store.historicalRevocationPreview.already_revoked ? '已经撤销' : '仅影响本次导入的来源贡献' }}</span>
              </div>
              <div class="revocation-facts">
                <span>受影响内容<b>{{ store.historicalRevocationPreview.impact.affected_content_count }}</b></span>
                <span>撤销后隐藏<b>{{ store.historicalRevocationPreview.impact.hidden_content_count }}</b></span>
                <span>其它来源保留<b>{{ store.historicalRevocationPreview.impact.retained_shared_content_count }}</b></span>
                <span>无法自动恢复<b>{{ store.historicalRevocationPreview.impact.unreversible_content_count ?? 0 }}</b></span>
              </div>
              <AimaFeedbackBanner
                v-if="store.historicalRevocationPreview.already_revoked"
                tone="info"
              >
                这次导入已经撤销；导入记录、来源证据和审计历史仍会保留。
              </AimaFeedbackBanner>
              <AimaFeedbackBanner
                v-else-if="!store.historicalRevocationPreview.eligible"
                tone="warning"
              >
                {{ revocationUnavailableMessage }}
              </AimaFeedbackBanner>
              <label
                v-else
                class="revocation-reason"
              >
                <span>撤销原因（可选）</span>
                <textarea
                  v-model="revocationReason"
                  rows="2"
                  maxlength="2000"
                  placeholder="例如：误选了错误的数据目录"
                />
              </label>
            </section>

            <div
              v-if="store.historicalCampaignItems.length"
              class="campaign-items"
            >
              <div
                v-for="item in store.historicalCampaignItems"
                :key="item.id"
              >
                <span>{{ item.item_kind === 'source_file' ? '文件' : `数据分段 ${item.ordinal ?? ''}` }} · {{ item.relative_path }}</span>
                <b>{{ historicalItemStatusLabels[item.status] }}</b>
                <small v-if="item.status === 'failed'">处理失败；技术原因可在下方技术详情中查看。</small>
              </div>
            </div>
            <small v-if="store.historicalCampaignItemsHasMore">明细按失败和运行状态优先，当前仅展示前 200 条。</small>
            <small v-if="store.historicalCampaignConflictsHasMore">冲突明细当前仅展示前 500 条；总数以导入任务统计为准。</small>

            <details class="technical-details">
              <summary>技术详情</summary>
              <dl>
                <div><dt>导入任务标识</dt><dd>{{ store.selectedHistoricalCampaign.id }}</dd></div>
                <div><dt>原始状态</dt><dd>{{ store.selectedHistoricalCampaign.status }}</dd></div>
                <div><dt>来源路径</dt><dd>{{ store.selectedHistoricalCampaign.root_relative_path || '—' }}</dd></div>
              </dl>
              <div
                v-if="store.historicalCampaignItems.some((item) => item.error_code)"
                class="technical-errors"
              >
                <strong>失败项技术信息</strong>
                <span
                  v-for="item in store.historicalCampaignItems.filter((entry) => entry.error_code)"
                  :key="`technical-${item.id}`"
                >{{ item.relative_path }} · {{ item.error_code }}</span>
              </div>
            </details>
          </template>

          <AimaFeedbackBanner
            v-if="notice"
            tone="success"
            role="status"
          >
            {{ notice }}
          </AimaFeedbackBanner>
          <AimaFeedbackBanner
            v-if="validationError"
            tone="error"
            role="alert"
          >
            {{ validationError }}
          </AimaFeedbackBanner>
          <AimaFeedbackBanner
            v-if="store.error"
            tone="error"
            role="alert"
          >
            {{ store.error }}
          </AimaFeedbackBanner>
        </div>

        <footer>
          <AimaButton
            variant="secondary"
            size="small"
            :disabled="store.creatingHistorical"
            @click="emit('update:modelValue', false)"
          >
            关闭
          </AimaButton>
          <template v-if="!store.selectedHistoricalCampaign">
            <AimaButton
              class="create-button"
              variant="primary"
              :disabled="!canCreate"
              :aria-busy="store.creatingHistorical"
              @click="createCampaign"
            >
              {{ store.creatingHistorical ? '正在创建…' : '创建并预检' }}
            </AimaButton>
          </template>
          <template v-else>
            <AimaButton
              v-if="canCancel"
              variant="secondary"
              size="small"
              :disabled="store.actingHistorical"
              @click="cancelCampaign"
            >
              取消任务
            </AimaButton>
            <AimaButton
              v-if="canRetry"
              variant="secondary"
              size="small"
              :disabled="store.actingHistorical"
              @click="retryCampaign"
            >
              重试失败项
            </AimaButton>
            <AimaButton
              v-if="canPreviewRevocation && !store.historicalRevocationPreview"
              variant="secondary"
              size="small"
              :disabled="store.previewingHistoricalRevocation"
              @click="previewRevocation"
            >
              {{ store.previewingHistoricalRevocation ? '正在评估…' : '评估撤销' }}
            </AimaButton>
            <AimaButton
              v-if="store.historicalRevocationPreview?.eligible && !store.historicalRevocationPreview.already_revoked"
              class="danger-action"
              variant="secondary"
              size="small"
              :disabled="store.revokingHistorical"
              @click="revokeImport"
            >
              {{ store.revokingHistorical ? '正在撤销…' : '撤销本次导入' }}
            </AimaButton>
            <AimaButton
              v-if="canViewContents"
              variant="secondary"
              size="small"
              @click="viewCampaignContents"
            >
              查看导入内容
            </AimaButton>
            <AimaButton
              v-if="store.selectedHistoricalCampaign.can_start"
              variant="primary"
              :disabled="store.actingHistorical"
              @click="startCampaign"
            >
              开始导入
            </AimaButton>
          </template>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-layer { position: fixed; z-index: 140; inset: 0; display: grid; place-items: center; background: rgb(17 22 37 / 94%); }
.dialog { display: grid; width: min(840px, calc(100vw - 48px)); height: min(800px, calc(100vh - 48px)); grid-template-rows: 76px minmax(0, 1fr) 72px; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 11px; background: var(--aima-surface); box-shadow: 0 22px 60px rgb(22 29 43 / 22%); }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 16px 22px 12px; border-bottom: 1px solid var(--aima-border); }
header h2 { margin: 0; color: var(--aima-text); font-size: 19px; line-height: 26px; }
header p { max-width: 620px; margin: 2px 0 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.dialog-body { display: flex; min-height: 0; flex-direction: column; gap: 20px; padding: 16px 22px; overflow-x: hidden; overflow-y: auto; }
.source-tabs { display: flex; min-height: 40px; gap: 8px; }
.source-tabs button { min-height: 40px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; }
.source-tabs button.selected { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.policy-panel, .source-panel, .pack-panel, .campaign-panel, .campaign-history, .campaign-stats, .revocation-panel { padding: 12px 13px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: var(--aima-surface); }
.policy-panel > strong, .pack-panel > strong, .campaign-history > strong, .campaign-stats > strong { color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }
.policy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px; }
.policy-grid label { position: relative; display: block; min-height: 58px; padding: 9px 11px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); cursor: pointer; }
.policy-grid label.selected { border-color: var(--aima-primary); background: #fff5f8; }
.policy-grid input { position: absolute; opacity: 0; }
.policy-grid span { display: grid; gap: 3px; }
.policy-grid b { color: var(--aima-text); font-size: 13px; font-weight: 500; }
.policy-grid label.selected b { color: var(--aima-primary); }
.policy-grid small, .source-help { margin: 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.section-heading { display: flex; align-items: center; gap: 16px; }
.section-heading strong { min-width: 0; overflow: hidden; color: var(--aima-text); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.section-heading > span, .section-heading code { min-width: 0; flex: 1; overflow: hidden; color: var(--aima-text-disabled); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.source-help { margin-top: 4px; }
.local-actions { display: flex; gap: 12px; margin-top: 10px; }
.local-actions label { display: inline-flex; height: 32px; align-items: center; padding: 0 14px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); color: var(--aima-text); background: var(--aima-surface); cursor: pointer; font-size: 13px; }
.local-actions .folder-action { border-color: transparent; }
.local-actions input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.local-file-list { display: grid; gap: 5px; max-height: 112px; margin-top: 10px; overflow: auto; padding: 10px; border-radius: var(--aima-radius-control); background: #f8fafc; font-size: 12px; }
.local-file-list span { display: flex; justify-content: space-between; gap: 12px; }
.local-file-list small { color: var(--aima-text-disabled); }
.directory-list, .pack-list { display: grid; gap: 6px; max-height: 180px; margin-top: 10px; overflow: auto; }
.directory-entry { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px; min-height: 40px; padding: 0 8px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.directory-entry label, .pack-list label { display: flex; min-width: 0; align-items: center; gap: 9px; color: var(--aima-text-secondary); cursor: pointer; font-size: 13px; }
.directory-entry input, .pack-list input, .recursive-option input { accent-color: var(--aima-primary); }
.directory-entry label span, .pack-list label span { display: flex; min-width: 0; flex: 1; align-items: center; justify-content: space-between; gap: 10px; }
.directory-entry b, .pack-list b { overflow: hidden; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.directory-entry small, .pack-list small { color: var(--aima-text-disabled); font-size: 11px; font-weight: 400; }
.directory-more { margin-top: 8px; }
.recursive-option { display: flex; align-items: center; gap: 8px; margin-top: 10px; color: var(--aima-text-secondary); font-size: 12px; }
.recursive-option small { margin-left: auto; color: var(--aima-text-disabled); font-size: 11px; }
.pack-list { grid-template-columns: 1fr 1fr; }
.pack-list label { min-height: 32px; }
.pack-help { display: block; margin-top: 8px; color: var(--aima-text-disabled); font-size: 11px; }
.empty-state { margin: 10px 0 0; color: var(--aima-text-muted); font-size: 12px; }
.campaign-history > div { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin-top: 10px; }
.campaign-history button { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; padding: 7px 0; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 11px; text-align: left; }
.campaign-history button.selected { color: var(--aima-primary); }
.campaign-name { display: grid; min-width: 0; gap: 2px; }
.campaign-name b, .campaign-name small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.campaign-name b { color: var(--aima-text-secondary); font-size: 12px; font-weight: 500; }
.campaign-name small { color: var(--aima-text-disabled); font-size: 10px; }
.campaign-status { margin-top: 10px; padding: 12px 13px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); color: var(--aima-text-muted); background: #f8fafc; font-size: 11px; }
.campaign-status--ready, .campaign-status--succeeded { border-color: var(--aima-success); }
.campaign-status--failed, .campaign-status--partial_failed { border-color: var(--aima-danger); }
.campaign-facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px 20px; margin-top: 12px; }
.campaign-facts span { display: flex; gap: 6px; color: var(--aima-text-disabled); font-size: 11px; }
.campaign-facts b { color: var(--aima-text-secondary); font-weight: 500; }
.campaign-progresses { display: grid; gap: 12px; margin: 18px 0; }
.campaign-stats > div, .revocation-facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
.campaign-stats span, .revocation-facts span { display: grid; gap: 4px; padding: 9px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); color: var(--aima-text-disabled); font-size: 11px; }
.campaign-stats b, .revocation-facts b { color: var(--aima-primary); font-size: 16px; }
.revocation-panel { display: grid; gap: 10px; }
.revocation-reason { display: grid; gap: 6px; color: var(--aima-text-muted); font-size: 11px; }
.revocation-reason textarea { resize: vertical; padding: 8px 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); color: var(--aima-text-secondary); font: inherit; font-size: 12px; }
.campaign-items { display: grid; gap: 6px; max-height: 150px; overflow: auto; }
.campaign-items > div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 10px; padding: 7px 9px; border-radius: var(--aima-radius-control); background: #f8fafc; font-size: 11px; }
.campaign-items span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.campaign-items small { grid-column: 1 / -1; color: var(--aima-danger); }
.technical-details { padding: 10px 12px; border: 1px dashed var(--aima-border-strong); border-radius: var(--aima-radius-control); color: var(--aima-text-muted); font-size: 11px; }
.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-weight: 500; }
.technical-details dl { display: grid; gap: 7px; margin: 10px 0 0; }
.technical-details dl div { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 8px; }
.technical-details dt { color: var(--aima-text-disabled); }
.technical-details dd { margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); }
.technical-errors { display: grid; gap: 5px; margin-top: 12px; }
.technical-errors span { overflow-wrap: anywhere; color: var(--aima-danger); }
footer { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
footer :deep(.aima-button.is-primary) { min-width: 88px; }
.danger-action { border-color: var(--aima-danger) !important; color: var(--aima-danger) !important; }
button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 760px) { .policy-grid, .pack-list, .campaign-history > div, .campaign-facts, .campaign-stats > div, .revocation-facts { grid-template-columns: 1fr; } }
</style>