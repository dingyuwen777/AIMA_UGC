<script setup lang="ts">
import { watch } from 'vue'
import type { AnalysisContentRunPreviewResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  preview: AnalysisContentRunPreviewResponse | null
  previewing: boolean
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  preview: [scope: 'selected']
  submit: []
}>()

watch(() => props.modelValue, (open) => {
  if (open && props.selectedCount > 0 && props.selectedCount <= 1000) {
    emit('preview', 'selected')
  }
})
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
              创建 AI Analysis Run
            </h2>
            <p>先预检已选内容，再由后台冻结目标并拆分有界 Shard。</p>
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
          <div class="selection-summary">
            <strong>已选内容</strong>
            <small>{{ selectedCount }} 条；按当前内容版本冻结目标，单次最多 1000 条</small>
          </div>
          <p class="scope-note">
            查询范围 Run 暂未开放；待真实模型质量与容量验证完成后再评估。
          </p>
          <p class="cost-note">
            此操作可能产生模型调用费用。只有点击确认后才会创建 Analysis Run；导入和采集不会自动触发付费分析。
          </p>
          <div
            v-if="previewing"
            class="preview"
            role="status"
          >
            正在预检目标与模型配置…
          </div>
          <div
            v-else-if="preview"
            class="preview"
          >
            <strong>预检目标 {{ preview.target_count }} 条，拆分 {{ preview.shard_count }} 个 Shard</strong>
            <span>每个 Shard {{ preview.shard_size }} 条 · {{ preview.model_provider }} / {{ preview.model }}</span>
            <span>Prompt {{ preview.prompt_version }} · 配置哈希 {{ preview.configuration_hash.slice(0, 12) }}…</span>
            <small>{{ preview.cost_estimate_note }}</small>
          </div>
        </div>
        <footer>
          <AimaButton @click="emit('update:modelValue', false)">
            取消
          </AimaButton>
          <AimaButton
            variant="primary"
            :disabled="previewing || !preview || submitting || selectedCount === 0 || selectedCount > 1000"
            @click="emit('submit')"
          >
            {{ submitting ? '正在提交…' : '确认并创建 Analysis Run' }}
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
.selection-summary { display: grid; min-height: 60px; align-content: center; gap: 4px; padding: 10px 14px; border: 1px solid var(--aima-primary); border-radius: 8px; background: var(--aima-primary-soft); }
.selection-summary strong { color: var(--aima-text); font-size: 12px; }
.selection-summary small { color: var(--aima-text-muted); font-size: 10px; }
.scope-note { margin: 0; color: var(--aima-text-muted); font-size: 10px; line-height: 16px; }
.cost-note { margin: 0; padding: 8px 12px; border: 1px solid #f2d48a; border-radius: 6px; color: #b7791f; background: #fff9e9; font-size: 10px; line-height: 17px; }
.preview { display: grid; min-height: 88px; align-content: center; gap: 5px; padding: 10px 12px; border: 1px solid #bfd5f5; border-radius: 6px; color: #32618f; background: #f2f7fd; font-size: 10px; line-height: 14px; }
.preview strong { font-size: 11px; }
.preview small { color: var(--aima-text-disabled); font-size: 9px; }
footer { display: flex; min-height: 68px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 22px; border-top: 1px solid var(--aima-border); }
footer :deep(.aima-button) { height: 38px; }
@media (min-height: 500px) {
  .modal { transform: translateY(-17px); }
}
</style>
