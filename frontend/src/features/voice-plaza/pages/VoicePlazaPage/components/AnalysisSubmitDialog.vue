<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: boolean; selectedCount: number; submitting: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [open: boolean]; submit: [scope: 'query' | 'selected'] }>()
const scope = ref<'query' | 'selected'>('selected')

watch(() => props.modelValue, (open) => { if (open) scope.value = props.selectedCount > 0 ? 'selected' : 'query' })
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
              提交 AI 情感 / 标签分析
            </h2><p>创建持久化 Job，在后台调用已配置模型。</p>
          </div><button
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header><div class="body">
          <label :class="{ active: scope === 'selected', disabled: selectedCount === 0 }"><input
            v-model="scope"
            type="radio"
            value="selected"
            :disabled="selectedCount === 0"
          ><span><strong>已选内容</strong><small>{{ selectedCount }} 条；按当前内容版本冻结目标</small></span></label><label :class="{ active: scope === 'query' }"><input
            v-model="scope"
            type="radio"
            value="query"
          ><span><strong>全部查询结果</strong><small>按当前筛选条件冻结目标，不受后续列表变化影响</small></span></label><p class="cost-note">
            此操作可能产生模型调用费用。只有点击确认后才会创建分析 Job；导入和采集不会自动触发付费分析。
          </p>
        </div><footer>
          <button
            type="button"
            @click="emit('update:modelValue', false)"
          >
            取消
          </button><button
            class="primary"
            type="button"
            :disabled="submitting"
            @click="emit('submit', scope)"
          >
            {{ submitting ? '正在提交…' : '确认并创建 Job' }}
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
.body label { display: flex; align-items: center; gap: 13px; padding: 14px; border: 1px solid #dfe3ea; border-radius: 8px; cursor: pointer; }
.body label.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.body label.disabled { opacity: .55; cursor: default; }
.body input { accent-color: var(--aima-primary); }
.body strong, .body small { display: block; }
.body strong { color: #354052; }
.body small { margin-top: 5px; color: #7d8696; }
.cost-note { margin: 5px 0 0; padding: 11px; border: 1px solid #f2d48a; border-radius: 6px; color: #8a6518; background: #fff9e9; font-size: 12px; line-height: 1.55; }
footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 22px; border-top: 1px solid var(--aima-border); }
footer button { height: 38px; padding: 0 18px; border: 1px solid #d9dee7; border-radius: 6px; background: #fff; cursor: pointer; }
footer .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
button:disabled { opacity: .6; cursor: default; }
</style>
