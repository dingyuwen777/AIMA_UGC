<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

type FileSlot = 'current' | 'previous'
type ReportFormStatus = 'idle' | 'validation-error' | 'backend-unavailable'

const currentFile = ref<File | null>(null)
const previousFile = ref<File | null>(null)
const startDate = ref('')
const endDate = ref('')
const status = ref<ReportFormStatus>('idle')
const validationMessage = ref('')
const currentInput = ref<HTMLInputElement | null>(null)
const previousInput = ref<HTMLInputElement | null>(null)

const emit = defineEmits<{
  'dirty-change': [dirty: boolean]
}>()

/** 任何本地报告输入都属于尚未提交的草稿；后端未接入时尤其不能静默丢失。 */
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

const submitLabel = computed(() => status.value === 'backend-unavailable'
  ? '后端服务未接入'
  : '生成报告并同步到飞书')

/** 将本地报告草稿状态上送给管理员 Page Owner。 */
watch(navigationDirty, (dirty) => emit('dirty-change', dirty), { immediate: true })

/** 返回文件槽当前持有的本地文件。 */
function selectedFile(slot: FileSlot): File | null {
  return slot === 'current' ? currentFile.value : previousFile.value
}

/** 用户修改输入后回到可校验状态，不保留过期反馈。 */
function clearFeedback(): void {
  status.value = 'idle'
  validationMessage.value = ''
}

/** 仅接受本地可确认的 .xlsx 扩展名，不冒充工作簿内容校验。 */
function setFile(slot: FileSlot, file: File | null): void {
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

/** 将原生文件选择结果写入对应报告周期。 */
function onFileChange(slot: FileSlot, event: Event): void {
  const input = event.currentTarget as HTMLInputElement
  setFile(slot, input.files?.[0] ?? null)
}

/** 支持把单个 XLSX 直接拖入对应报告周期。 */
function onFileDrop(slot: FileSlot, event: DragEvent): void {
  setFile(slot, event.dataTransfer?.files[0] ?? null)
}

/** 清空原生文件控件，保证移除后仍可重新选择同名文件。 */
function clearNativeInput(slot: FileSlot): void {
  const input = slot === 'current' ? currentInput.value : previousInput.value
  if (input) input.value = ''
}

/** 移除一个已选文件，并清除与旧输入相关的反馈。 */
function removeFile(slot: FileSlot): void {
  setFile(slot, null)
  clearNativeInput(slot)
}

/** 重新打开对应的系统文件选择器。 */
function replaceFile(slot: FileSlot): void {
  const input = slot === 'current' ? currentInput.value : previousInput.value
  input?.click()
}

/** 重置本地输入；当前阶段不会触发报告任务或服务端写请求。 */
function resetForm(): void {
  currentFile.value = null
  previousFile.value = null
  startDate.value = ''
  endDate.value = ''
  clearFeedback()
  clearNativeInput('current')
  clearNativeInput('previous')
}

/** 执行本地表单校验，并在真实后端缺席时明确停止提交。 */
function submitReport(): void {
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
  status.value = 'backend-unavailable'
}
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
                @click="replaceFile('current')"
              >
                替换
              </button>
              <button
                type="button"
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
                @click="replaceFile('previous')"
              >
                替换
              </button>
              <button
                type="button"
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
            aria-label="开始日期"
            @input="clearFeedback"
          >
        </label>
        <label>
          <span>结束日期 <b aria-hidden="true">*</b></span>
          <input
            v-model="endDate"
            type="date"
            aria-label="结束日期"
            @input="clearFeedback"
          >
        </label>
      </div>
    </section>

    <AimaFeedbackBanner
      v-if="status === 'validation-error'"
      tone="error"
      role="alert"
    >
      {{ validationMessage }}
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else-if="status === 'backend-unavailable'"
      tone="warning"
      role="alert"
    >
      前端表单已准备就绪；报告服务尚未接入，暂不可提交。请勿生成假任务或假飞书链接。
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-else
      tone="info"
    >
      提交后任务将在后台执行。报告生成完成后，会同时上传至飞书文档和飞书多维表格。
    </AimaFeedbackBanner>

    <footer class="report-actions">
      <AimaButton
        variant="secondary"
        @click="resetForm"
      >
        重置
      </AimaButton>
      <AimaButton
        variant="primary"
        :disabled="!formComplete || status === 'backend-unavailable'"
        @click="submitReport"
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
