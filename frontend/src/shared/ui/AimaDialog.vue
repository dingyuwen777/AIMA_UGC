<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ modelValue: boolean; label: string; width?: string }>(), { width: '620px' })
const emit = defineEmits<{ 'update:modelValue': [open: boolean] }>()
const dialog = ref<HTMLDialogElement | null>(null)

/** 使用浏览器原生模态焦点隔离、Escape 和焦点返回，不修改页面全局键盘行为。 */
watch(() => props.modelValue, async (open) => {
  await nextTick()
  if (open && !dialog.value?.open) dialog.value?.showModal()
  else if (!open && dialog.value?.open) dialog.value.close()
}, { immediate: true })

/** 只有点击面板外部的遮罩才关闭，面板内部空白保留当前输入。 */
function backdrop(event: MouseEvent): void {
  if (event.target !== dialog.value || !dialog.value) return
  const box = dialog.value.getBoundingClientRect()
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) emit('update:modelValue', false)
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      v-bind="$attrs"
      class="aima-dialog"
      :style="{ width }"
      :aria-label="label"
      @close="emit('update:modelValue', false)"
      @click="backdrop"
    >
      <header
        v-if="$slots.header"
        class="aima-dialog-header"
      >
        <slot name="header" />
      </header>
      <div class="aima-dialog-body">
        <slot />
      </div>
      <footer
        v-if="$slots.footer"
        class="aima-dialog-footer"
      >
        <slot name="footer" />
      </footer>
    </dialog>
  </Teleport>
</template>

<style>
.aima-dialog { max-width: calc(100vw - 32px); max-height: calc(100dvh - 48px); padding: 0; border: 1px solid var(--aima-border); border-radius: 12px; color: var(--aima-text); background: var(--aima-surface); box-shadow: var(--aima-shadow-floating); }
.aima-dialog[open] { display: flex; flex-direction: column; }
.aima-dialog::backdrop { background: rgb(17 22 37 / 42%); }
.aima-dialog-header, .aima-dialog-footer { flex: none; }
.aima-dialog-body { min-height: 0; overflow-y: auto; }
</style>
