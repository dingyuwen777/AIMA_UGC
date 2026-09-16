<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  label: string
  width?: string
  height?: string
  closeOnBackdrop?: boolean
  closeDisabled?: boolean
}>(), {
  width: '840px',
  height: '800px',
  closeOnBackdrop: false,
  closeDisabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const panel = ref<HTMLElement | null>(null)
let returnFocus: HTMLElement | null = null

/** 共享复杂模态框只管理遮罩、视口约束和固定头尾；业务动作与可关闭资格由调用方传入。 */
function close(): void {
  if (props.closeDisabled) return
  emit('update:modelValue', false)
}

/** 打开时记录触发控件并把焦点移入模态框。 */
async function focusPanel(): Promise<void> {
  if (typeof document === 'undefined' || typeof HTMLElement === 'undefined') return
  if (!returnFocus) {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  }
  await nextTick()
  panel.value?.focus({ preventScroll: true })
}

/** 关闭或被父组件卸载时，恢复触发控件焦点。 */
function restoreTriggerFocus(): void {
  const target = returnFocus
  returnFocus = null
  if (target?.isConnected) target.focus({ preventScroll: true })
}

/** 只让当前 DOM 中最上层的模态元素响应全局 Escape，嵌套详情不会误关底层抽屉。 */
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
      class="aima-modal-layer"
      role="presentation"
      @click.self="closeOnBackdrop && close()"
    >
      <section
        ref="panel"
        class="aima-modal-container"
        :style="{
          width: `min(${width}, calc(100vw - 48px))`,
          height: `min(${height}, calc(100dvh - 48px))`,
        }"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        tabindex="-1"
        @keydown.esc.stop="close"
      >
        <div
          v-if="$slots.header"
          class="aima-modal-header"
        >
          <slot
            name="header"
            :close="close"
          />
        </div>
        <div class="aima-modal-body">
          <slot />
        </div>
        <div
          v-if="$slots.footer"
          class="aima-modal-footer"
        >
          <slot
            name="footer"
            :close="close"
          />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.aima-modal-layer {
  position: fixed;
  z-index: 140;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgb(17 22 37 / 50%);
}
.aima-modal-container {
  display: flex;
  max-width: calc(100vw - 48px);
  max-height: calc(100dvh - 48px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--aima-color-border-default);
  border-radius: var(--aima-radius-xl);
  outline: 0;
  background: var(--aima-color-bg-white);
  box-shadow: 0 22px 60px rgb(22 29 43 / 22%);
}
.aima-modal-header,
.aima-modal-footer { flex: none; }
.aima-modal-body {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
}
</style>
