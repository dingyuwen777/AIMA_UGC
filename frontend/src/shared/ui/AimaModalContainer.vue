<script setup lang="ts">
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

/** 共享复杂模态框只管理遮罩、视口约束和固定头尾；业务动作与可关闭资格由调用方传入。 */
function close(): void {
  if (props.closeDisabled) return
  emit('update:modelValue', false)
}
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
        class="aima-modal-container"
        :style="{
          width: `min(${width}, calc(100vw - 48px))`,
          height: `min(${height}, calc(100dvh - 48px))`,
        }"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        @keydown.esc="close"
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
