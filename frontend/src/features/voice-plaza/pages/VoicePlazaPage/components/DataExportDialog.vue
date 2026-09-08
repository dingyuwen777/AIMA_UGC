<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  DataExportResponse,
  ExportColumnCatalogResponse,
  ExportColumnKey,
} from '../../../../../generated/api/client'
import { exportArtifactRetention } from '../../../../../shared/artifactRetention'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { formatDateTime, formatNumber } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  pageCount: number
  items: DataExportResponse[]
  columnCatalog: ExportColumnCatalogResponse | null
  submitting: boolean
  error?: string | null
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  submit: [scope: 'query' | 'selected' | 'page', columns: ExportColumnKey[]]
  refresh: []
  download: [item: DataExportResponse]
}>()
const scope = ref<'query' | 'selected' | 'page'>('selected')
const selectedColumns = ref<ExportColumnKey[]>([])
const columnsEdited = ref(false)

watch(() => props.modelValue, (open) => {
  if (open) {
    columnsEdited.value = false
    scope.value = props.selectedCount > 0 ? 'selected' : props.pageCount > 0 ? 'page' : 'query'
    selectedColumns.value = (props.columnCatalog?.columns ?? [])
      .filter((item) => item.default_selected)
      .map((item) => item.key as ExportColumnKey)
  }
})

/** 异步目录首次到达时补齐默认列；刷新目录不覆盖用户已修改的选择。 */
watch(() => props.columnCatalog, (catalog) => {
  if (props.modelValue && !columnsEdited.value && catalog) {
    selectedColumns.value = catalog.columns.filter((column) => column.default_selected).map((column) => column.key as ExportColumnKey)
  }
})

const canSubmit = computed(() => {
  if (selectedColumns.value.length === 0) return false
  if (scope.value === 'selected') return props.selectedCount > 0
  return props.pageCount > 0
})

function toggleColumn(key: string): void {
  columnsEdited.value = true
  const typedKey = key as ExportColumnKey
  selectedColumns.value = selectedColumns.value.includes(typedKey)
    ? selectedColumns.value.filter((item) => item !== typedKey)
    : [...selectedColumns.value, typedKey]
}

const statusLabels = {
  queued: '排队中',
  running: '导出中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

/** 复用统一 Artifact 保留策略计算当前导出记录的下载有效期。 */
function retention(item: DataExportResponse) {
  return exportArtifactRetention(item.completed_at)
}

/** 只有 Job 成功且 Artifact 尚未过期时允许下载。 */
function canDownload(item: DataExportResponse): boolean {
  const current = retention(item)
  return item.job.status === 'succeeded' && current.expiresAt !== null && !current.expired
}
</script>

<template>
  <AimaDialog
    :model-value="modelValue"
    label="导出声音记录"
    width="560px"
    class="voice-export-modal"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header>
        <div>
          <h2 id="export-title">
            导出声音记录
          </h2>
          <p>选择导出范围和字段，系统将在后台生成可下载的 Excel 文件。</p>
        </div>

        <button
          class="close-button"
          type="button"
          aria-label="关闭"
          @click="emit('update:modelValue', false)"
        >
          <AimaIcon
            name="close"
            :size="20"
          />
        </button>
      </header>
    </template>
    <div class="body">
      <p
        v-if="error"
        role="alert"
        class="request-error"
      >
        {{ error }}
      </p>
      <h3>导出范围</h3>
      <div class="choice-grid">
        <label :class="{ active: scope === 'selected', disabled: selectedCount === 0 }">
          <input
            v-model="scope"
            type="radio"
            value="selected"
            :disabled="selectedCount === 0"
          >
          <span><strong>已选内容</strong><small>{{ selectedCount }} 条</small></span>
        </label>
        <label :class="{ active: scope === 'page', disabled: pageCount === 0 }">
          <input
            v-model="scope"
            type="radio"
            value="page"
            :disabled="pageCount === 0"
          >
          <span><strong>当前页内容</strong><small>冻结已加载 {{ pageCount }} 条</small></span>
        </label>
        <label :class="{ active: scope === 'query', disabled: pageCount === 0 }">
          <input
            v-model="scope"
            type="radio"
            value="query"
            :disabled="pageCount === 0"
          >
          <span><strong>全部查询结果</strong><small>{{ pageCount > 0 ? '按当前筛选条件冻结' : '当前筛选没有可导出内容' }}</small></span>
        </label>
      </div>
      <section class="column-picker">
        <header><strong>导出字段</strong><span>{{ columnCatalog?.columns.length ?? '—' }} 个可选字段</span></header>
        <div>
          <label
            v-for="column in columnCatalog?.columns ?? []"
            :key="column.key"
          >
            <input
              type="checkbox"
              :checked="selectedColumns.includes(column.key as ExportColumnKey)"
              @change="toggleColumn(column.key)"
            >
            <span>{{ column.label }}</span>
            <small v-if="column.sensitive">敏感列</small>
          </label>
          <em v-if="!columnCatalog">列目录加载中…</em>
        </div>
      </section>
      <p class="analysis-note">
        未完成 AI 打标的内容不会被丢弃：仍会导出，AI 情感和标签列留空，并在结果统计中提示。
      </p>
      <p class="retention-note">
        Excel 导出文件自生成完成后保留 7 天。过期后文件会自动清理，导出记录仍保留；需要时可重新创建导出。
      </p>
      <div class="records-title">
        <strong>最近导出记录</strong>
        <AimaButton
          variant="text"
          size="small"
          icon="refresh"
          @click="emit('refresh')"
        >
          刷新
        </AimaButton>
      </div>
      <div class="records">
        <article
          v-for="item in items"
          :key="item.id"
        >
          <div class="record-info">
            <strong>{{ item.filename || `声音广场导出 ${item.id.slice(0, 8)}` }}</strong>
            <small>{{ formatDateTime(item.created_at) }} · {{ statusLabels[item.job.status] }}</small>
            <TaskProgressBar
              compact
              :label="`导出 ${item.id.slice(0, 8)} 进度`"
              :value="item.job.progress"
              :tone="item.job.status === 'succeeded' ? 'success' : item.job.status === 'failed' ? 'danger' : 'primary'"
            />
            <span v-if="item.stats">内容 {{ formatNumber(item.stats.content_count) }} · 已打标 {{ formatNumber(item.stats.analyzed_count) }} · 未打标 {{ formatNumber(item.stats.unanalyzed_count) }}</span>
            <span
              v-if="retention(item).expiresAt"
              :class="{ expired: retention(item).expired }"
            >{{ retention(item).expired ? '下载已过期' : `下载有效期至 ${formatDateTime(retention(item).expiresAt)}` }}</span>
            <span
              v-else-if="item.job.status !== 'succeeded'"
              class="pending-artifact"
            >文件尚未生成</span>
            <span
              v-if="item.job.error_code"
              class="error"
            >导出遇到问题，请重试；如持续失败，请联系管理员查看技术详情。</span>
            <details
              v-if="item.job.error_code"
              class="technical-details"
            >
              <summary>技术详情</summary>
              <code>{{ item.job.error_code }}</code>
            </details>
          </div>
          <AimaButton
            size="small"
            variant="outline"
            icon="download"
            :disabled="!canDownload(item)"
            @click="emit('download', item)"
          >
            {{ retention(item).expired ? '已过期' : item.job.status === 'running' || item.job.status === 'queued' ? '导出中' : '下载' }}
          </AimaButton>
        </article>
        <p
          v-if="items.length === 0"
          class="empty"
        >
          暂无导出记录。
        </p>
      </div>
    </div>
    <template #footer>
      <footer>
        <AimaButton @click="emit('update:modelValue', false)">
          取消
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="submitting || !canSubmit"
          @click="emit('submit', scope, selectedColumns)"
        >
          {{ submitting ? '正在创建…' : scope === 'query' ? '开始导出查询结果' : `开始导出 ${scope === 'selected' ? selectedCount : pageCount} 条` }}
        </AimaButton>
      </footer>
    </template>
  </AimaDialog>
</template>

<style scoped>
header { display: flex; min-height: 82px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 26px; }
header p { margin: 5px 0 0; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.close-button { display: grid; width: 32px; height: 32px; place-items: center; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.body { min-height: 0; padding: 18px 22px; overflow-y: auto; }
.choice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.choice-grid label { display: flex; min-height: 82px; align-items: flex-start; gap: 8px; padding: 12px 13px; border: 1px solid var(--aima-border); border-radius: 7px; cursor: pointer; }
.choice-grid label.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.choice-grid label.disabled { opacity: .55; cursor: default; }
.choice-grid input { margin: 2px 0 0; accent-color: var(--aima-primary); }
.choice-grid strong,
.choice-grid small { display: block; }
.choice-grid strong { color: var(--aima-text); font-size: 11px; }
.choice-grid small { margin-top: 5px; color: var(--aima-text-muted); font-size: 9px; }
.column-picker { margin-top: 10px; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: 7px; }
.column-picker header { display: flex; min-height: auto; align-items: center; justify-content: space-between; padding: 0 0 8px; border: 0; }
.column-picker header strong { color: var(--aima-text); font-size: 11px; }
.column-picker header span { color: var(--aima-text-disabled); font-size: 9px; }
.column-picker > div { display: flex; flex-wrap: wrap; gap: 6px; }
.column-picker label { display: inline-flex; min-height: 27px; align-items: center; gap: 5px; padding: 0 7px; border: 1px solid var(--aima-border); border-radius: 5px; color: var(--aima-text-secondary); font-size: 10px; }
.column-picker input { margin: 0; accent-color: var(--aima-primary); }
.column-picker small { color: var(--aima-danger); font-size: 8px; }
.column-picker em { color: var(--aima-text-disabled); font-size: 10px; font-style: normal; }
.analysis-note,
.retention-note { margin: 8px 0 0; padding: 8px 10px; border: 1px solid #bcd5f5; border-radius: 6px; color: #39678f; background: #f2f7fd; font-size: 10px; line-height: 14px; }
.retention-note { border-color: #e2d7a4; color: #6e5c20; background: #fffaf0; line-height: 17px; }
.records-title { display: flex; min-height: 30px; align-items: center; justify-content: space-between; margin-top: 8px; }
.records-title strong { color: var(--aima-text); font-size: 12px; }
.records-title :deep(.aima-button) { font-size: 10px; }
.records { max-height: 232px; overflow-y: auto; border: 1px solid var(--aima-border); border-radius: 7px; }
.records article { display: flex; min-height: 114px; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 12px; border-bottom: 1px solid #edf0f4; }
.records article:last-child { border-bottom: 0; }
.record-info { display: grid; min-width: 0; flex: 1; gap: 4px; }
.record-info > strong,
.record-info > small,
.record-info > span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.record-info > strong { color: var(--aima-text); font-size: 11px; }
.record-info > small,
.record-info > span { color: var(--aima-text-muted); font-size: 9px; }
.records :deep(.task-progress) { width: min(280px, 100%); margin-top: 1px; }
.records :deep(.task-progress__heading) { display: none; }
.records :deep(.task-progress__track) { height: 7px; }
.records .error,
.records .expired { color: var(--aima-danger); }
.technical-details { color: var(--aima-text-muted); font-size: 9px; }
.technical-details summary { cursor: pointer; }
.technical-details code { display: block; margin-top: 4px; color: var(--aima-text-secondary); white-space: normal; }
.pending-artifact { color: var(--aima-text-disabled) !important; }
.empty { padding: 24px; color: var(--aima-text-disabled); text-align: center; }
footer { display: flex; min-height: 68px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); }
footer :deep(.aima-button) { height: 38px; }
.request-error { color: var(--aima-danger); font-size: 12px; line-height: 18px; }
header { min-height: 90px; padding: 24px 28px 12px; border: 0; }
h2 { font-size: 16px; }
.body { max-height: 490px; padding: 0 28px 20px; }
h3 { margin: 0 0 12px; font-size: 13px; }
.column-picker { margin: 24px 0; padding: 0; border: 0; }
.column-picker header { padding: 0 0 12px; }
.column-picker header strong { font-size: 13px; }
.column-picker > div { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 16px; border-radius: 8px; background: #f7f9fb; }
.column-picker label { min-height: 32px; padding: 0; border: 0; font-size: 12px; }
.column-picker input { width: 16px; height: 16px; flex: none; }
.retention-note { margin-top: 12px; padding: 14px 12px; font-size: 11px; }
footer { padding: 18px 28px 28px; border: 0; }
:global(.voice-export-modal) { height: 669px; }
:global(.voice-export-modal > .aima-dialog-body) { flex: 1; }
.body { min-height: 0; max-height: none; }
</style>
