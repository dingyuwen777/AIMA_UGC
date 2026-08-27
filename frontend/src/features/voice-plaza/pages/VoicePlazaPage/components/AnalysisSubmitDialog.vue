<script setup lang="ts">
import { watch } from 'vue'
import type { AnalysisContentRunPreviewResponse } from '../../../../../generated/api/client'

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
      /><section
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-title"
      >
        <header>
          <div>
            <h2 id="analysis-title">
              创建 AI Analysis Run
            </h2><p>先预检已选内容，再由后台冻结目标并拆分有界 Shard。</p>
          </div><button
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header><div class="body">
          <div class="selection-summary">
            <span><strong>已选内容</strong><small>{{ selectedCount }} 条；按当前内容版本冻结目标，单次最多 1000 条</small></span>
          </div><p class="scope-note">
            查询范围 Run 暂未开放；待真实模型质量与容量验证完成后再评估。
          </p><p class="cost-note">
            此操作可能产生模型调用费用。只有点击确认后才会创建 Analysis Run；导入和采集不会自动触发付费分析。
          </p><div
            v-if="previewing"
            class="preview"
            role="status"
          >
            正在预检目标与模型配置…
          </div><div
            v-else-if="preview"
            class="preview"
          >
            <strong>预检目标 {{ preview.target_count }} 条，拆分 {{ preview.shard_count }} 个 Shard</strong>
            <span>每个 Shard {{ preview.shard_size }} 条 · {{ preview.model_provider }} / {{ preview.model }}</span>
            <span>Prompt {{ preview.prompt_version }} · 配置哈希 {{ preview.configuration_hash.slice(0, 12) }}…</span>
            <small>{{ preview.cost_estimate_note }}</small>
          </div>
        </div><footer>
          <button
            type="button"
            @click="emit('update:modelValue', false)"
          >
            取消
          </button><button
            class="primary"
            type="button"
            :disabled="previewing || !preview || submitting || selectedCount === 0 || selectedCount > 1000"
            @click="emit('submit')"
          >
            {{ submitting ? '正在提交…' : '确认并创建 Analysis Run' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-layer { position: fixed; z-index: 130; inset: 0; display: grid; place-items: center; }
.backdrop { position: absolute; inset: 0; border: 0; background: rgb(25 32 45 / 48%); }
.modal { position: relative; width: 540px; overflow: hidden; border-radius: 11px; background: #fff; box-shadow: 0 22px 58px rgb(20 28 42 / 22%); }
header { display: flex; align-items: start; justify-content: space-between; padding: 21px 22px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; font-size: 19px; }
header p { margin: 6px 0 0; color: #7b8494; font-size: 12px; }
header button { border: 0; color: #7d8695; background: transparent; font-size: 25px; cursor: pointer; }
.body { display: grid; gap: 10px; padding: 20px 22px; }
.selection-summary { display: flex; align-items: center; gap: 13px; padding: 14px; border: 1px solid var(--aima-primary); border-radius: 8px; background: var(--aima-primary-soft); }
.body strong, .body small { display: block; }
.body strong { color: #354052; }
.body small { margin-top: 5px; color: #7d8696; }
.scope-note { margin: 0; color: #697386; font-size: 12px; line-height: 1.55; }
.cost-note { margin: 5px 0 0; padding: 11px; border: 1px solid #f2d48a; border-radius: 6px; color: #8a6518; background: #fff9e9; font-size: 12px; line-height: 1.55; }
.preview { display: grid; gap: 5px; padding: 12px; border: 1px solid #bfd5f5; border-radius: 6px; color: #32618f; background: #f2f7fd; font-size: 12px; line-height: 1.5; }
.preview strong, .preview span, .preview small { display: block; }
.preview small { color: #66778c; }
footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 22px; border-top: 1px solid var(--aima-border); }
footer button { height: 38px; padding: 0 18px; border: 1px solid #d9dee7; border-radius: 6px; background: #fff; cursor: pointer; }
footer .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
button:disabled { opacity: .6; cursor: default; }
</style>
