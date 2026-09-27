<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

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
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const open = ref(false)
const position = ref({ left: '0px', top: '0px' })

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

/** Popover 进入浏览器顶层，避免横向滚动的筛选条裁切选项。 */
function togglePanel(): void {
  if (open.value) {
    panel.value?.hidePopover()
    return
  }
  const box = trigger.value?.getBoundingClientRect()
  if (!box) return
  const left = Math.max(12, Math.min(box.left, window.innerWidth - 232))
  const top = box.bottom + 275 < window.innerHeight
    ? box.bottom + 5
    : Math.max(12, box.top - 275)
  position.value = { left: `${left}px`, top: `${top}px` }
  panel.value?.showPopover()
}

/** 页面滚动时关闭浮层；用户在选项面板内滚动时保持可操作。 */
function dismissOnScroll(event: Event): void {
  if (event.target instanceof Node && panel.value?.contains(event.target)) return
  if (open.value) panel.value?.hidePopover()
}

onMounted(() => window.addEventListener('scroll', dismissOnScroll, true))
onBeforeUnmount(() => window.removeEventListener('scroll', dismissOnScroll, true))
</script>

<template>
  <div class="workbench-select">
    <button
      ref="trigger"
      class="workbench-select__trigger"
      type="button"
      :aria-label="label"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :disabled="disabled"
      @click="togglePanel"
    >
      <span>{{ label }}：</span><strong>{{ selectedText }}</strong><i>▾</i>
    </button>
    <div
      ref="panel"
      popover="auto"
      class="workbench-select__panel"
      :style="position"
      role="dialog"
      :aria-label="`选择${label}`"
      @toggle="open = $event.newState === 'open'"
    >
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
  </div>
</template>

<style scoped>
.workbench-select__trigger {
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
  white-space: nowrap;
  font-size: 11px;
}
.workbench-select__trigger strong { max-width: 118px; overflow: hidden; color: var(--aima-text); font-weight: 600; text-overflow: ellipsis; }
.workbench-select__trigger i { margin-left: 2px; color: var(--aima-text-disabled); font-style: normal; }
.workbench-select__trigger[aria-expanded="true"] { border-color: var(--aima-primary); box-shadow: 0 0 0 2px var(--aima-color-focus-ring); }
.workbench-select__panel {
  position: fixed;
  display: grid;
  width: 220px;
  max-height: min(270px, calc(100dvh - 24px));
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
