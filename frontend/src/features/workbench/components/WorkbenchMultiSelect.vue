<script setup lang="ts">
import { computed } from 'vue'

export interface WorkbenchSelectOption {
  value: string
  label: string
}

const props = withDefaults(defineProps<{
  label: string
  options: WorkbenchSelectOption[]
  modelValue: string[]
  allLabel?: string
  disabled?: boolean
}>(), {
  allLabel: '全部',
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const selectedText = computed(() => {
  if (props.modelValue.length === 0) return props.allLabel
  if (props.modelValue.length === 1) {
    return props.options.find((item) => item.value === props.modelValue[0])?.label ?? '已选 1 项'
  }
  return `已选 ${props.modelValue.length} 项`
})

/** 勾选变化后返回新数组，父级筛选快照始终保持不可变替换语义。 */
function toggle(value: string, checked: boolean): void {
  const next = checked
    ? [...new Set([...props.modelValue, value])]
    : props.modelValue.filter((item) => item !== value)
  emit('update:modelValue', next)
}

/** 全选按钮在“已有任何选择”时清空，否则选择当前动态目录全部值。 */
function toggleAll(): void {
  emit('update:modelValue', props.modelValue.length ? [] : props.options.map((item) => item.value))
}
</script>

<template>
  <details class="workbench-select">
    <summary :aria-label="label">
      <span>{{ label }}：</span><strong>{{ selectedText }}</strong><i>▾</i>
    </summary>
    <div class="workbench-select__panel">
      <button
        class="workbench-select__all"
        type="button"
        :disabled="disabled || options.length === 0"
        @click="toggleAll"
      >
        {{ modelValue.length ? '清空选择' : '全部选择' }}
      </button>
      <label
        v-for="option in options"
        :key="option.value"
      >
        <input
          type="checkbox"
          :disabled="disabled"
          :checked="modelValue.includes(option.value)"
          @change="toggle(option.value, ($event.target as HTMLInputElement).checked)"
        >
        <span>{{ option.label }}</span>
      </label>
      <p v-if="options.length === 0">
        暂无可选项
      </p>
    </div>
  </details>
</template>

<style scoped>
.workbench-select { position: relative; }
.workbench-select summary {
  display: flex;
  height: 30px;
  align-items: center;
  gap: 3px;
  padding: 0 9px;
  border: 1px solid var(--aima-border-strong);
  border-radius: var(--aima-radius-md);
  color: var(--aima-text-disabled);
  background: var(--aima-surface);
  cursor: pointer;
  list-style: none;
  white-space: nowrap;
  font-size: 11px;
}
.workbench-select summary::-webkit-details-marker { display: none; }
.workbench-select summary strong { max-width: 118px; overflow: hidden; color: var(--aima-text); font-weight: 600; text-overflow: ellipsis; }
.workbench-select summary i { margin-left: 2px; color: var(--aima-text-disabled); font-style: normal; }
.workbench-select[open] summary { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-color-focus-ring); }
.workbench-select__panel {
  position: absolute;
  z-index: 60;
  top: calc(100% + 5px);
  left: 0;
  display: grid;
  width: 220px;
  max-height: 270px;
  gap: 1px;
  overflow: auto;
  padding: 6px;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: var(--aima-surface);
  box-shadow: var(--aima-shadow-floating);
}
.workbench-select__panel label { display: flex; min-height: 30px; align-items: center; gap: 7px; padding: 4px 7px; border-radius: 5px; color: var(--aima-text); cursor: pointer; font-size: 11px; }
.workbench-select__panel label:hover { background: var(--aima-color-bg-hover); }
.workbench-select__panel input { accent-color: var(--aima-primary); }
.workbench-select__panel p { margin: 10px; color: var(--aima-text-disabled); text-align: center; font-size: 11px; }
.workbench-select__all { min-height: 28px; border: 0; border-bottom: 1px solid var(--aima-border); color: var(--aima-primary); background: transparent; cursor: pointer; text-align: left; font-size: 11px; }
</style>
