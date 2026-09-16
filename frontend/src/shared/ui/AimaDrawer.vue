<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

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

/** 打开时把键盘焦点移入抽屉，关闭后恢复到触发控件，保证 Escape 与连续操作可达。 */
watch(() => props.modelValue, async (visible, previous) => {
  if (visible) {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    panel.value?.focus({ preventScroll: true })
    return
  }
  if (!previous || !returnFocus) return
  const target = returnFocus
  returnFocus = null
  await nextTick()
  if (target.isConnected) target.focus({ preventScroll: true })
}, { flush: 'post' })
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
  border: 1px solid var(--aima-color-border-default);
  border-radius: var(--aima-radius-xl) 0 0 var(--aima-radius-xl);
  outline: 0;
  background: var(--aima-color-bg-white);
  box-shadow: -10px 0 30px rgb(23 32 51 / 12%);
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
