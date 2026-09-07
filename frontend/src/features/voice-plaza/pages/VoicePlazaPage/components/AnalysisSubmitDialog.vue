<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AnalysisContentRunPreviewResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

type AnalysisScope = 'selected' | 'all'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  preview: AnalysisContentRunPreviewResponse | null
  previewing: boolean
  submitting: boolean
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
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="modal-layer"
    >
      <button
        class="backdrop"
        type="button"
        aria-label="关闭 AI 打标弹窗"
        @click="emit('update:modelValue', false)"
      />
      <section
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-title"
      >
        <header>
          <div>
            <h2 id="analysis-title">
              创建 AI 打标任务
            </h2>
            <p>先预估待处理内容，再由后台分批完成 AI 打标。</p>
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
        <div class="body">
          <fieldset class="scope-picker">
            <legend>打标范围</legend>
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
                <strong>已选内容</strong>
                <small>{{ selectedCount }} 条；显式选择单次最多 1000 条</small>
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
                <strong>全部数据</strong>
                <small>对系统当前全部内容打标，不受本页筛选或已加载分页限制</small>
              </span>
            </label>
          </fieldset>
          <p class="scope-note">
            “全部数据”由后台按当前数据范围处理，不需要浏览器加载全部内容。
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
            <strong>预计处理 {{ preview.target_count }} 条，系统将分 {{ preview.shard_count }} 批完成</strong>
            <span>每批最多 {{ preview.shard_size }} 条</span>
            <small>{{ preview.cost_estimate_note }}</small>
            <details class="technical-details">
              <summary>技术详情</summary>
              <span>模型：{{ preview.model_provider }} / {{ preview.model }}</span>
              <span>Prompt：{{ preview.prompt_version }}</span>
              <span>配置哈希：{{ preview.configuration_hash.slice(0, 12) }}…</span>
            </details>
          </div>
        </div>
        <footer>
          <AimaButton @click="emit('update:modelValue', false)">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="previewing || !preview || submitting"
            @click="emit('submit')"
          >
            {{ submitting ? '正在提交…' : '确认并创建任务' }}
          </AimaButton>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-layer { position: fixed; z-index: 130; inset: 0; display: grid; place-items: center; }
.backdrop { position: absolute; inset: 0; border: 0; background: rgb(25 32 45 / 46%); }
.modal { position: relative; display: grid; width: min(540px, calc(100vw - 32px)); height: min(446px, calc(100vh - 32px)); overflow: hidden; border-radius: 11px; background: var(--aima-surface); box-shadow: 0 22px 58px rgb(20 28 42 / 22%); }
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
  .modal { transform: translateY(-17px); }
}
</style>
