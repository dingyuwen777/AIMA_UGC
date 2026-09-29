<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type {
  FeishuPublicationJobResponse,
  FeishuReportPublicationResult,
} from '../../../../../generated/api/client'
import { apiErrorMessage } from '../../../../../shared/api/http'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import {
  createReportPublication,
  fetchReportPublicationJob,
} from '../../../api'

type FileSlot = 'current' | 'previous'
type ReportFormStatus =
  | 'idle'
  | 'validation-error'
  | 'submitting'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

const REPORT_JOB_STORAGE_KEY = 'aima.admin.report-publication-job-id'

const currentFile = ref<File | null>(null)
const previousFile = ref<File | null>(null)
const startDate = ref('')
const endDate = ref('')
const status = ref<ReportFormStatus>('idle')
const validationMessage = ref('')
const job = ref<FeishuPublicationJobResponse | null>(null)
const jobId = ref<string | null>(null)
const currentInput = ref<HTMLInputElement | null>(null)
const previousInput = ref<HTMLInputElement | null>(null)
const pollError = ref('')
const pollHandle = ref<ReturnType<typeof setInterval> | null>(null)
let pollInFlight = false
let pollFailureCount = 0

const emit = defineEmits<{
  'dirty-change': [dirty: boolean]
}>()

const navigationDirty = computed(() => Boolean(
  currentFile.value
  || previousFile.value
  || startDate.value
  || endDate.value,
))

const formComplete = computed(() => Boolean(
  currentFile.value
  && previousFile.value
  && startDate.value
  && endDate.value,
))

const busy = computed(() => ['submitting', 'queued', 'running'].includes(status.value))
const reportResult = computed<FeishuReportPublicationResult | null>(() => {
  const result = job.value?.result
  return result?.kind === 'report' ? result : null
})
const statusLabel = computed(() => {
  const labels: Partial<Record<ReportFormStatus, string>> = {
    submitting: '正在上传',
    queued: '排队中',
    running: '生成中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status.value] ?? ''
})
const statusMessage = computed(() => {
  if (status.value === 'submitting') return '正在上传两份报告文件…'
  if (pollError.value) return '报告任务状态同步中，正在重试…'
  return `报告任务${statusLabel.value}，请稍候。`
})
const submitLabel = computed(() => busy.value ? statusLabel.value : '生成报告并同步到飞书')

watch(navigationDirty, (dirty) => emit('dirty-change', dirty), { immediate: true })

function selectedFile(slot: FileSlot): File | null {
  return slot === 'current' ? currentFile.value : previousFile.value
}

function clearFeedback(): void {
  if (busy.value) return
  status.value = 'idle'
  validationMessage.value = ''
  pollError.value = ''
  job.value = null
  jobId.value = null
  clearStoredJobId()
}

function readStoredJobId(): string | null {
  try {
    return window.sessionStorage.getItem(REPORT_JOB_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeJobId(id: string): void {
  try {
    window.sessionStorage.setItem(REPORT_JOB_STORAGE_KEY, id)
  } catch {
    // 状态持久化失败不应阻止当前页面继续轮询。
  }
}

function clearStoredJobId(): void {
  try {
    window.sessionStorage.removeItem(REPORT_JOB_STORAGE_KEY)
  } catch {
    // 某些浏览器隐私模式可能禁止 sessionStorage。
  }
}

function setFile(slot: FileSlot, file: File | null): void {
  if (busy.value) return
  clearFeedback()
  if (file && !file.name.toLocaleLowerCase().endsWith('.xlsx')) {
    validationMessage.value = '表单校验未通过：报告文件必须使用 .xlsx 格式。'
    status.value = 'validation-error'
    clearNativeInput(slot)
    return
  }
  if (slot === 'current') currentFile.value = file
  else previousFile.value = file
}

function onFileChange(slot: FileSlot, event: Event): void {
  const input = event.currentTarget as HTMLInputElement
  setFile(slot, input.files?.[0] ?? null)
}

function onFileDrop(slot: FileSlot, event: DragEvent): void {
  setFile(slot, event.dataTransfer?.files[0] ?? null)
}

function clearNativeInput(slot: FileSlot): void {
  const input = slot === 'current' ? currentInput.value : previousInput.value
  if (input) input.value = ''
}

function removeFile(slot: FileSlot): void {
  setFile(slot, null)
  clearNativeInput(slot)
}

function replaceFile(slot: FileSlot): void {
  const input = slot === 'current' ? currentInput.value : previousInput.value
  input?.click()
}

function stopPolling(): void {
  if (pollHandle.value !== null) clearInterval(pollHandle.value)
  pollHandle.value = null
}

function applyJob(next: FeishuPublicationJobResponse): void {
  job.value = next
  jobId.value = next.id
  status.value = next.status
  pollFailureCount = 0
  pollError.value = ''
  if (['succeeded', 'failed', 'cancelled'].includes(next.status)) {
    stopPolling()
    clearStoredJobId()
  } else {
    storeJobId(next.id)
  }
}

async function pollJob(): Promise<void> {
  const currentJobId = job.value?.id ?? jobId.value
  if (!currentJobId || pollInFlight || !['queued', 'running'].includes(status.value)) return
  pollInFlight = true
  try {
    applyJob(await fetchReportPublicationJob(currentJobId))
  } catch (error) {
    pollFailureCount += 1
    pollError.value = `状态同步失败（第 ${pollFailureCount} 次），正在重试：${apiErrorMessage(error)}`
  } finally {
    pollInFlight = false
  }
}

function startPolling(): void {
  stopPolling()
  // 先立即读取一次，避免提交后至少等待一个完整轮询周期。
  void pollJob()
  pollHandle.value = setInterval(() => void pollJob(), 3000)
}

function handleVisibilityChange(): void {
  if (document.visibilityState === 'visible') void pollJob()
}

async function restoreStoredJob(): Promise<void> {
  const storedJobId = readStoredJobId()
  if (!storedJobId) return
  jobId.value = storedJobId
  status.value = 'queued'
  try {
    applyJob(await fetchReportPublicationJob(storedJobId))
  } catch (error) {
    pollError.value = `状态同步失败，正在重试：${apiErrorMessage(error)}`
  }
  if (['queued', 'running'].includes(status.value)) startPolling()
}

function resetForm(): void {
  if (busy.value) return
  stopPolling()
  currentFile.value = null
  previousFile.value = null
  startDate.value = ''
  endDate.value = ''
  status.value = 'idle'
  validationMessage.value = ''
  pollError.value = ''
  job.value = null
  jobId.value = null
  clearStoredJobId()
  clearNativeInput('current')
  clearNativeInput('previous')
}

async function submitReport(): Promise<void> {
  clearFeedback()
  if (!formComplete.value || !currentFile.value || !previousFile.value) {
    validationMessage.value = '表单校验未通过：请补充两份 .xlsx 文件和完整日期范围。'
    status.value = 'validation-error'
    return
  }
  if (endDate.value < startDate.value) {
    validationMessage.value = '表单校验未通过：请确认两份文件均为 .xlsx，且结束日期不早于开始日期。'
    status.value = 'validation-error'
    return
  }
  status.value = 'submitting'
  try {
    const created = await createReportPublication({
      current_file: currentFile.value,
      previous_file: previousFile.value,
      start_date: startDate.value,
      end_date: endDate.value,
    })
    jobId.value = created.job_id
    storeJobId(created.job_id)
    status.value = 'queued'
    try {
      applyJob(await fetchReportPublicationJob(created.job_id))
    } catch (error) {
      // POST 已成功，必须保留 job_id 并继续轮询；首次 GET 失败不能
      // 让用户重复提交产生第二个后台任务。
      pollError.value = apiErrorMessage(error)
    }
    if (['queued', 'running'].includes(status.value)) {
      startPolling()
    }
  } catch (error) {
    status.value = 'failed'
    validationMessage.value = apiErrorMessage(error)
  }
}

onMounted(() => {
  void restoreStoredJob()
  window.addEventListener('focus', handleVisibilityChange)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  window.removeEventListener('focus', handleVisibilityChange)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <section
    class="report-strategy-card"
    aria-labelledby="report-strategy-title"
  >
    <header class="report-header">
      <h2 id="report-strategy-title">
        飞书报告发布
      </h2>
      <p>上传本期和上期 XLSX，填写报告日期范围后，系统将生成报告并同步到飞书文档和飞书多维表格。</p>
    </header>

    <section
      class="form-section"
      aria-labelledby="report-files-title"
    >
      <div class="section-heading">
        <h3 id="report-files-title">
          报告文件
        </h3>
        <p>分别选择本期与上期带周期标识的 Excel 文件。</p>
      </div>
      <div class="upload-grid">
        <div class="upload-field">
          <label for="report-current-file">本期 XLSX <span aria-hidden="true">*</span></label>
          <input
            id="report-current-file"
            ref="currentInput"
            class="visually-hidden"
            type="file"
            :disabled="busy"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            aria-label="本期 XLSX"
            @change="onFileChange('current', $event)"
          >
          <div
            v-if="selectedFile('current')"
            class="selected-file"
          >
            <AimaIcon
              name="task"
              :size="22"
            />
            <div>
              <strong>{{ selectedFile('current')?.name }}</strong>
              <span>XLSX 文件 · 已完成扩展名检查</span>
            </div>
            <div class="file-actions">
              <button
                type="button"
                :disabled="busy"
                @click="replaceFile('current')"
              >
                替换
              </button>
              <button
                type="button"
                :disabled="busy"
                @click="removeFile('current')"
              >
                移除
              </button>
            </div>
          </div>
          <label
            v-else
            class="upload-zone"
            for="report-current-file"
            @dragover.prevent
            @drop.prevent="onFileDrop('current', $event)"
          >
            <AimaIcon
              name="plus"
              :size="20"
            />
            <strong>点击或将 XLSX 文件拖拽到这里</strong>
            <span>仅支持 .xlsx；内容将在后端接入后校验</span>
          </label>
        </div>

        <div class="upload-field">
          <label for="report-previous-file">上期 XLSX <span aria-hidden="true">*</span></label>
          <input
            id="report-previous-file"
            ref="previousInput"
            class="visually-hidden"
            type="file"
            :disabled="busy"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            aria-label="上期 XLSX"
            @change="onFileChange('previous', $event)"
          >
          <div
            v-if="selectedFile('previous')"
            class="selected-file"
          >
            <AimaIcon
              name="task"
              :size="22"
            />
            <div>
              <strong>{{ selectedFile('previous')?.name }}</strong>
              <span>XLSX 文件 · 已完成扩展名检查</span>
            </div>
            <div class="file-actions">
              <button
                type="button"
                :disabled="busy"
                @click="replaceFile('previous')"
              >
                替换
              </button>
              <button
                type="button"
                :disabled="busy"
                @click="removeFile('previous')"
              >
                移除
              </button>
            </div>
          </div>
          <label
            v-else
            class="upload-zone"
            for="report-previous-file"
            @dragover.prevent
            @drop.prevent="onFileDrop('previous', $event)"
          >
            <AimaIcon
              name="plus"
              :size="20"
            />
            <strong>点击或将 XLSX 文件拖拽到这里</strong>
            <span>仅支持 .xlsx；内容将在后端接入后校验</span>
          </label>
        </div>
      </div>
    </section>

    <section
      class="form-section"
      aria-labelledby="report-period-title"
    >
      <div class="section-heading">
        <h3 id="report-period-title">
          报告日期范围
        </h3>
        <p>日期将作为本次报告的统计周期。</p>
      </div>
      <div class="date-grid">
        <label>
          <span>开始日期 <b aria-hidden="true">*</b></span>
          <input
            v-model="startDate"
            type="date"
            :disabled="busy"
            aria-label="开始日期"
            @input="clearFeedback"
          >
        </label>
        <label>
          <span>结束日期 <b aria-hidden="true">*</b></span>
          <input
            v-model="endDate"
            type="date"
            :disabled="busy"
            aria-label="结束日期"
            @input="clearFeedback"
          >
        </label>
      </div>
    </section>

    <AimaFeedbackBanner
      v-if="status === 'validation-error' || status === 'failed'"
      tone="error"
      role="alert"
    >
      {{ validationMessage || `报告任务失败：${job?.error_code || '请稍后重试。'}` }}
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else-if="status === 'succeeded'"
      tone="success"
      role="status"
    >
      {{ reportResult?.dry_run
        ? 'Dry Run 已完成：报告和代表性内容已生成，未写入飞书。'
        : '报告已生成，并已同步到飞书文档和飞书多维表格。' }}
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else-if="status === 'cancelled'"
      tone="warning"
      role="alert"
    >
      报告任务已取消。
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else-if="status === 'submitting' || status === 'queued' || status === 'running'"
      tone="info"
    >
      {{ statusMessage }}
      <span v-if="pollError">{{ pollError }}</span>
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else
      tone="info"
    >
      提交后任务将在后台执行。报告生成完成后，会同时上传至飞书文档和飞书多维表格。
    </AimaFeedbackBanner>

    <section
      v-if="job && ['submitting', 'queued', 'running'].includes(status)"
      class="report-progress"
      aria-label="报告任务进度"
    >
      <TaskProgressBar
        :label="`报告任务 ${statusLabel}`"
        :value="job.progress"
        :detail="job.source_filenames?.join('、') ?? ''"
        :tone="status === 'running' ? 'primary' : 'warning'"
      />
    </section>

    <section
      v-if="status === 'succeeded' && reportResult"
      class="report-result"
      aria-label="报告任务结果"
    >
      <div>
        <strong>处理结果</strong>
        <span>内容 {{ reportResult.content_rows }} 条 · 标签 {{ reportResult.label_rows }} 条 · 评论 {{ reportResult.comment_rows }} 条 · 代表性内容 {{ reportResult.representative_count }} 条</span>
      </div>
      <div class="report-result-links">
        <a
          v-if="reportResult.native_document_url"
          :href="reportResult.native_document_url"
          target="_blank"
          rel="noopener noreferrer"
        >打开飞书报告</a>
        <a
          v-if="reportResult.representative_table_url
            && reportResult.representative_table_url !== reportResult.native_document_url"
          :href="reportResult.representative_table_url"
          target="_blank"
          rel="noopener noreferrer"
        >打开代表性多维表</a>
        <span
          v-if="reportResult.representative_table_url
            && reportResult.representative_table_url === reportResult.native_document_url"
        >代表性多维表已内嵌在报告第 6 节，可在报告中直接编辑。</span>
        <span v-if="reportResult.dry_run">Dry Run 未生成真实飞书链接。</span>
      </div>
    </section>

    <footer class="report-actions">
      <AimaButton
        variant="secondary"
        :disabled="busy"
        @click="resetForm"
      >
        重置
      </AimaButton>
      <AimaButton
        variant="primary"
        :disabled="!formComplete || busy"
        @click="void submitReport()"
      >
        {{ submitLabel }}
      </AimaButton>
    </footer>
  </section>
</template>

<style scoped>
.report-strategy-card {
  display: grid;
  min-width: 0;
  gap: 28px;
  padding: 28px;
  border: 1px solid var(--aima-border);
  border-radius: var(--aima-radius-xl);
  background: var(--aima-surface);
  box-shadow: 0 4px 14px rgb(23 35 61 / 5%);
}
.report-header h2,
.report-header p,
.section-heading h3,
.section-heading p { margin: 0; }
.report-header h2 {
  color: var(--aima-text);
  font-size: var(--aima-font-size-section-title);
  font-weight: 600;
  line-height: 26px;
}
.report-header p,
.section-heading p {
  margin-top: 6px;
  color: var(--aima-text-muted);
  font-size: var(--aima-font-size-body-small);
  line-height: 20px;
}
.form-section { display: grid; gap: 14px; }
.section-heading h3 {
  color: var(--aima-text);
  font-size: var(--aima-font-size-card-title);
  font-weight: 600;
  line-height: 22px;
}
.upload-grid,
.date-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.upload-field { display: grid; min-width: 0; gap: 8px; }
.upload-field > label:first-child,
.date-grid label > span {
  color: var(--aima-text-secondary);
  font-size: var(--aima-font-size-body-small);
  font-weight: 500;
  line-height: 20px;
}
.upload-field > label:first-child span,
.date-grid b { color: var(--aima-danger); font-weight: 500; }
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
.upload-zone,
.selected-file {
  min-height: 128px;
  border: 1px dashed var(--aima-border-strong);
  border-radius: var(--aima-radius-lg);
  background: var(--aima-surface-subtle);
}
.upload-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 7px;
  padding: 18px;
  color: var(--aima-text-muted);
  cursor: pointer;
  text-align: center;
}
.upload-zone strong {
  color: var(--aima-text-secondary);
  font-size: var(--aima-font-size-body-small);
  font-weight: 500;
}
.upload-zone span { font-size: var(--aima-font-size-caption); }
.upload-zone:hover {
  border-color: var(--aima-primary);
  color: var(--aima-primary);
  background: var(--aima-primary-soft);
}
.upload-field input:focus-visible + .upload-zone {
  outline: 2px solid var(--aima-primary-soft-strong);
  outline-offset: 2px;
}
.selected-file {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 18px;
  border-style: solid;
  color: var(--aima-primary);
}
.selected-file > div:nth-child(2) { display: grid; min-width: 0; gap: 4px; }
.selected-file strong {
  overflow: hidden;
  color: var(--aima-text);
  font-size: var(--aima-font-size-body);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected-file span { color: var(--aima-text-muted); font-size: var(--aima-font-size-caption); }
.file-actions { display: flex; gap: 8px; }
.file-actions button {
  padding: 4px;
  border: 0;
  color: var(--aima-primary);
  background: transparent;
  cursor: pointer;
  font-size: var(--aima-font-size-caption);
}
.file-actions button:focus-visible { outline: 2px solid var(--aima-primary-soft-strong); }
.date-grid label { display: grid; gap: 8px; }
.date-grid input {
  width: 100%;
  height: var(--aima-control-height-md);
  padding: 0 12px;
  border: 1px solid var(--aima-border-strong);
  border-radius: var(--aima-radius-lg);
  color: var(--aima-text);
  background: var(--aima-surface);
  font-size: var(--aima-font-size-control);
}
.date-grid input:focus {
  border-color: var(--aima-primary);
  outline: 2px solid var(--aima-primary-soft-strong);
}
.report-progress,
.report-result {
  padding: 14px 16px;
  border: 1px solid var(--aima-border);
  border-radius: var(--aima-radius-lg);
  background: var(--aima-surface-subtle);
}
.report-progress :deep(.task-progress__heading span) { color: var(--aima-text-muted); }
.report-result {
  display: grid;
  gap: 8px;
  color: var(--aima-text-muted);
  font-size: var(--aima-font-size-caption);
  line-height: 18px;
}
.report-result > div { display: flex; flex-wrap: wrap; gap: 8px; }
.report-result strong { color: var(--aima-text); font-size: var(--aima-font-size-body-small); }
.report-result-links { align-items: center; }
.report-result-links a {
  color: var(--aima-primary);
  font-weight: 500;
  text-decoration: none;
}
.report-result-links a:hover { text-decoration: underline; }
.report-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 900px) {
  .report-strategy-card { gap: 24px; padding: 20px; }
  .upload-grid,
  .date-grid { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .selected-file { grid-template-columns: auto minmax(0, 1fr); }
  .file-actions { grid-column: 1 / -1; justify-content: flex-end; }
  .report-actions { flex-direction: column-reverse; }
  .report-actions :deep(.aima-button) { width: 100%; }
}
</style>
