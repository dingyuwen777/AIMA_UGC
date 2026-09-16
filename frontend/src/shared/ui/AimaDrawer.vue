<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  label: string
  width?: string
  closeOnBackdrop?: boolean
}>(), {
  width: '510px',
  closeOnBackdrop: true,
})

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const panel = ref<HTMLElement | null>(null)
let returnFocus: HTMLElement | null = null

/** 关闭共享抽屉；业务动作、资格和保存状态继续由调用方维护。 */
function close(): void {
  emit('update:modelValue', false)
}

/** 打开时记录触发控件并把键盘焦点移入抽屉。 */
async function focusPanel(): Promise<void> {
  if (typeof document === 'undefined' || typeof HTMLElement === 'undefined') return
  if (!returnFocus) {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  }
  await nextTick()
  panel.value?.focus({ preventScroll: true })
}

/** 关闭或被父组件直接卸载时，把焦点还给原触发控件。 */
function restoreTriggerFocus(): void {
  const target = returnFocus
  returnFocus = null
  if (target?.isConnected) target.focus({ preventScroll: true })
}

/** 只让当前 DOM 中最上层的模态元素响应全局 Escape，避免嵌套弹层连带关闭。 */
function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !props.modelValue || !panel.value || typeof document === 'undefined') return
  const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
  if (dialogs.at(-1) !== panel.value) return
  event.preventDefault()
  event.stopImmediatePropagation()
  close()
}

watch(() => props.modelValue, async (visible, previous) => {
  if (visible && !previous) {
    await focusPanel()
    return
  }
  if (!visible && previous) {
    await nextTick()
    restoreTriggerFocus()
  }
}, { flush: 'post' })

onMounted(() => {
  document.addEventListener('keydown', onDocumentKeydown, true)
  if (props.modelValue) void focusPanel()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKeydown, true)
  restoreTriggerFocus()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="aima-drawer-layer"
      role="presentation"
      @click.self="closeOnBackdrop && close()"
    >
      <aside
        ref="panel"
        class="aima-drawer"
        :style="{ width: `min(${width}, 100vw)` }"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        tabindex="-1"
        @keydown.esc.stop="close"
      >
        <div
          v-if="$slots.header"
          class="aima-drawer-header"
        >
          <slot
            name="header"
            :close="close"
          />
        </div>
        <div class="aima-drawer-body">
          <slot />
        </div>
        <div
          v-if="$slots.footer"
          class="aima-drawer-footer"
        >
          <slot
            name="footer"
            :close="close"
          />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.aima-drawer-layer {
  position: fixed;
  z-index: 110;
  inset: 0;
  background: rgb(17 22 37 / 50%);
}
.aima-drawer {
  position: absolute;
  inset: 0 0 0 auto;
  display: flex;
  max-width: 100vw;
  height: 100dvh;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  border-radius: var(--aima-radius-xl) 0 0 var(--aima-radius-xl);
  outline: 0;
  background: var(--aima-color-bg-white);
  box-shadow: inset 0 0 0 1px var(--aima-color-border-default), -10px 0 30px rgb(23 32 51 / 12%);
}
.aima-drawer-header,
.aima-drawer-footer { flex: none; }
.aima-drawer-body {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
}
.aima-drawer-body > :deep(.body) {
  height: 100%;
  box-sizing: border-box;
}
</style>
