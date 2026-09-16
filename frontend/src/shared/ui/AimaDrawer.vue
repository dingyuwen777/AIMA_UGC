<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: boolean
  label: string
  width?: string
  closeOnBackdrop?: boolean
}>(), {
  width: '510px',
  closeOnBackdrop: true,
})

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

/** 共享抽屉只拥有关闭交互和滚动边界，业务页签、动作与状态继续由调用方维护。 */
function close(): void {
  emit('update:modelValue', false)
}
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
        class="aima-drawer"
        :style="{ width: `min(${width}, 100vw)` }"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        @keydown.esc="close"
      >
        <div
          v-if="$slots.header"
          class="aima-drawer-header"
        >
          <slot name="header" :close="close" />
        </div>
        <div class="aima-drawer-body">
          <slot />
        </div>
        <div
          v-if="$slots.footer"
          class="aima-drawer-footer"
        >
          <slot name="footer" :close="close" />
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
</style>
