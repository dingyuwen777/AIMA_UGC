<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

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
const position = ref({ left: '12px', top: '12px', maxHeight: '270px' })
let positionedTrigger: { left: number; top: number } | null = null
const nativePopoverSupported = typeof HTMLElement !== 'undefined'
  && typeof HTMLElement.prototype.showPopover === 'function'

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

/** 根据真实触发器、面板与视口尺寸选择展开方向并约束可滚动高度。 */
function updatePosition(): void {
  const box = trigger.value?.getBoundingClientRect()
  const menu = panel.value
  if (!box || !menu) return
  const viewportGap = 12
  const anchorGap = 5
  const panelWidth = menu.offsetWidth || 232
  const desiredHeight = Math.min(menu.scrollHeight || 270, 270, window.innerHeight - viewportGap * 2)
  const below = window.innerHeight - box.bottom - viewportGap - anchorGap
  const above = box.top - viewportGap - anchorGap
  const placeBelow = below >= Math.min(desiredHeight, 160) || below >= above
  const availableHeight = Math.max(48, placeBelow ? below : above)
  const actualHeight = Math.min(desiredHeight, availableHeight)
  const left = Math.max(
    viewportGap,
    Math.min(box.left, window.innerWidth - panelWidth - viewportGap),
  )
  const top = placeBelow
    ? box.bottom + anchorGap
    : Math.max(viewportGap, box.top - actualHeight - anchorGap)
  position.value = {
    left: `${Math.round(left)}px`,
    top: `${Math.round(top)}px`,
    maxHeight: `${Math.round(actualHeight)}px`,
  }
  positionedTrigger = { left: box.left, top: box.top }
}

/** 显式打开面板；原生 Popover 只增强顶层和 light-dismiss，不拥有显示事实。 */
async function showPanel(): Promise<void> {
  open.value = true
  await nextTick()
  if (nativePopoverSupported && panel.value && !panel.value.matches(':popover-open')) {
    panel.value.showPopover()
  }
  updatePosition()
}

/** 关闭原生或 fallback 面板，并按键盘操作需要恢复触发器焦点。 */
function hidePanel(restoreFocus = false): void {
  if (nativePopoverSupported && panel.value?.matches(':popover-open')) {
    panel.value.hidePopover()
  }
  open.value = false
  positionedTrigger = null
  if (restoreFocus) trigger.value?.focus()
}

/** 切换当前组件自己的面板，不依赖浏览器初始 Popover 样式。 */
function togglePanel(): void {
  if (open.value) hidePanel()
  else void showPanel()
}

/** 只有会移动触发器的滚动才关闭浮层，忽略面板和相邻模块自己的内部滚动。 */
function dismissOnScroll(event: Event): void {
  if (!open.value) return
  const scrollTarget = event.target
  const triggerElement = trigger.value
  const triggerBox = triggerElement?.getBoundingClientRect()
  const triggerMoved = !positionedTrigger || !triggerBox
    || Math.abs(triggerBox.left - positionedTrigger.left) > 0.5
    || Math.abs(triggerBox.top - positionedTrigger.top) > 0.5
  const movedByAncestorScroll = scrollTarget instanceof Node
    && triggerElement
    && scrollTarget.contains(triggerElement)
    && triggerMoved
  if (scrollTarget === window || movedByAncestorScroll) {
    hidePanel()
  }
}

/** fallback 模式补齐原生 Popover 的点击外部关闭。 */
function dismissOnPointerDown(event: PointerEvent): void {
  if (!open.value || !(event.target instanceof Node)) return
  if (panel.value?.contains(event.target) || trigger.value?.contains(event.target)) return
  hidePanel()
}

/** fallback 模式补齐 Escape 关闭并把焦点交还触发器。 */
function dismissOnKeyDown(event: KeyboardEvent): void {
  if (!open.value || event.key !== 'Escape') return
  event.preventDefault()
  hidePanel(true)
}

/** 原生 light-dismiss 后同步 Vue 状态，关闭态样式不继续占据页面。 */
function syncNativeToggle(event: Event): void {
  const nextState = (event as ToggleEvent).newState
  open.value = nextState === 'open'
}

onMounted(() => {
  window.addEventListener('scroll', dismissOnScroll, true)
  window.addEventListener('resize', updatePosition)
  document.addEventListener('pointerdown', dismissOnPointerDown, true)
  document.addEventListener('keydown', dismissOnKeyDown)
})
onBeforeUnmount(() => {
  hidePanel()
  window.removeEventListener('scroll', dismissOnScroll, true)
  window.removeEventListener('resize', updatePosition)
  document.removeEventListener('pointerdown', dismissOnPointerDown, true)
  document.removeEventListener('keydown', dismissOnKeyDown)
})
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
      :popover="nativePopoverSupported ? 'auto' : undefined"
      class="workbench-select__panel"
      :class="{ 'workbench-select__panel--open': open }"
      :style="position"
      role="dialog"
      :aria-label="`选择${label}`"
      @toggle="syncNativeToggle"
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
  inset: auto;
  width: 220px;
  gap: 1px;
  overflow: auto;
  margin: 0;
  padding: 6px;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: var(--aima-surface);
  box-shadow: var(--aima-shadow-floating);
}
.workbench-select__panel:not(.workbench-select__panel--open) { display: none; }
.workbench-select__panel--open { display: grid; }
.workbench-select__panel label { display: flex; min-height: 30px; align-items: center; gap: 7px; padding: 4px 7px; border-radius: 5px; color: var(--aima-text); cursor: pointer; font-size: 11px; }
.workbench-select__panel label:hover { background: var(--aima-color-bg-hover); }
.workbench-select__panel input { accent-color: var(--aima-primary); }
.workbench-select__panel p { margin: 10px; color: var(--aima-text-disabled); text-align: center; font-size: 11px; }
.workbench-select__all { min-height: 28px; border: 0; border-bottom: 1px solid var(--aima-border); color: var(--aima-primary); background: transparent; cursor: pointer; text-align: left; font-size: 11px; }
</style>
