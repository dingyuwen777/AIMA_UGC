<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AnalysisContentRunPreviewResponse } from '../../../../../generated/api/client'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
type AnalysisScope = 'selected' | 'all'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  preview: AnalysisContentRunPreviewResponse | null
  previewing: boolean
  submitting: boolean
  error?: string | null
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  preview: [scope: AnalysisScope]
  submit: []
}>()

const scope = ref<AnalysisScope>('all')

/** 打开弹窗时优先使用有效显式选择，否则默认选择全部数据并立即预检。 */
watch(() => props.modelValue, (open) => {
  if (!open) return
  scope.value = props.selectedCount > 0 && props.selectedCount <= 1000 ? 'selected' : 'all'
  emit('preview', scope.value)
})

/** 切换目标范围后重新预检，避免沿用另一范围的数量与配置确认。 */
function selectScope(next: AnalysisScope): void {
  if (scope.value === next) return
  scope.value = next
  emit('preview', next)
}
</script>

<template>
  <AimaDialog
    :model-value="modelValue"
    label="开始 AI 分析"
    width="620px"
    class="voice-analysis-modal"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header>
        <div>
          <h2 id="analysis-title">
            开始 AI 分析
          </h2>
          <p>先预览分析范围和内容数量，确认后由系统在后台执行。</p>
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
      <fieldset class="scope-picker">
        <legend>当前范围：{{ scope === 'selected' ? `已选内容（${selectedCount} 条）` : '全部系统内容' }}</legend>
        <label
          class="scope-option"
          :class="{ 'scope-option--disabled': selectedCount === 0 || selectedCount > 1000 }"
        >
          <input
            type="radio"
            name="analysis-scope"
            value="selected"
            :checked="scope === 'selected'"
            :disabled="selectedCount === 0 || selectedCount > 1000"
            @change="selectScope('selected')"
          >
          <span>
            <strong>已选内容（{{ selectedCount }} 条）</strong>
            <small v-if="selectedCount > 1000">单次最多选择 1000 条</small>
          </span>
        </label>
        <label class="scope-option">
          <input
            type="radio"
            name="analysis-scope"
            value="all"
            :checked="scope === 'all'"
            @change="selectScope('all')"
          >
          <span>
            <strong>全部系统内容</strong>

          </span>
        </label>
      </fieldset>
      <p class="scope-note">
        全部范围包含系统中的全部当前内容，不受列表筛选和分页限制。
      </p>
      <div
        v-if="previewing"
        class="preview"
        role="status"
      >
        正在预估处理范围并检查模型配置…
      </div>
      <div
        v-else-if="preview"
        class="preview"
      >
        <span>预计分析 {{ preview.target_count }} 条内容 · {{ preview.shard_count }} 个分片 · 每片最多 {{ preview.shard_size }} 条</span>
        <small>{{ preview.cost_estimate_note }}</small>
        <details class="technical-details">
          <summary>高级配置</summary>
          <span>模型：{{ preview.model_provider }} / {{ preview.model }}</span>
          <span>Prompt：{{ preview.prompt_version }}</span>
          <span>配置哈希：{{ preview.configuration_hash.slice(0, 12) }}…</span>
        </details>
      </div>
    </div>
    <template #footer>
      <footer>
        <AimaButton @click="emit('update:modelValue', false)">
          取消
        </AimaButton>
        <AimaButton
          variant="primary"
          :disabled="previewing || !preview || submitting"
          @click="emit('submit')"
        >
          {{ submitting ? '正在提交…' : '确认开始分析' }}
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
.body { display: grid; min-height: 0; align-content: start; gap: 10px; padding: 18px 22px 16px; overflow-y: auto; }
.scope-picker { display: grid; gap: 8px; margin: 0; padding: 0; border: 0; }
.scope-picker legend { margin-bottom: 2px; color: var(--aima-text); font-size: 11px; font-weight: 700; }
.scope-option { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: center; min-height: 58px; padding: 9px 12px; border: 1px solid var(--aima-border); border-radius: 8px; cursor: pointer; }
.scope-option:has(input:checked) { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.scope-option input { margin: 0; accent-color: var(--aima-primary); }
.scope-option span { display: grid; gap: 3px; }
.scope-option strong { color: var(--aima-text); font-size: 11px; }
.scope-option small { color: var(--aima-text-muted); font-size: 10px; line-height: 15px; }
.scope-option--disabled { cursor: not-allowed; opacity: 0.55; }
.scope-note { margin: 0; color: var(--aima-text-muted); font-size: 10px; line-height: 16px; }
.preview { display: grid; min-height: 88px; align-content: center; gap: 5px; padding: 10px 12px; border: 1px solid #bfd5f5; border-radius: 6px; color: #32618f; background: #f2f7fd; font-size: 10px; line-height: 14px; }
.preview strong { font-size: 11px; }
.preview small { color: var(--aima-text-disabled); font-size: 9px; }
.technical-details { color: #527293; }
.technical-details summary { width: max-content; cursor: pointer; font-weight: 600; }
.technical-details span { display: block; margin-top: 3px; overflow-wrap: anywhere; }
footer { display: flex; min-height: 68px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); }
footer :deep(.aima-button) { height: 38px; }
@media (min-height: 500px) {

}
.request-error { color: var(--aima-danger); font-size: 12px; line-height: 18px; }
.body { min-height: 360px; gap: 12px; }
.scope-picker { grid-template-columns: 1fr 1fr; gap: 12px; }
.scope-picker legend { margin-bottom: 12px; color: var(--aima-text-muted); font-size: 13px; font-weight: 400; }
.scope-option { position: relative; display: flex; justify-content: center; min-height: 38px; padding: 8px 10px; border-radius: 6px; }
.scope-option input { position: absolute; opacity: 0; }
.scope-option:has(input:focus-visible) { outline: 2px solid var(--aima-primary); outline-offset: 2px; }
.scope-option strong { font-size: 13px; font-weight: 500; }
.preview { min-height: 0; padding: 0; border: 0; color: var(--aima-text-muted); background: transparent; font-size: 11px; }
.preview small { font-size: 11px; line-height: 18px; }
.technical-details summary { margin-top: 6px; padding: 7px 24px; border: 1px solid var(--aima-border-strong); border-radius: 6px; color: var(--aima-text); font-size: 13px; list-style: none; }
footer :deep(.is-primary) { min-width: 190px; }
@media (max-height: 570px) { .body { min-height: 0; } }
:global(.voice-analysis-modal) { height: 510px; }
:global(.voice-analysis-modal > .aima-dialog-body) { flex: 1; }
.body { min-height: 0; max-height: none; }
</style>
