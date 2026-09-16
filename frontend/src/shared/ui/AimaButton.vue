<script setup lang="ts">
import AimaIcon, { type AimaIconName } from './AimaIcon.vue'

withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'outline' | 'text'
  size?: 'small' | 'medium'
  icon?: AimaIconName
  type?: 'button' | 'submit' | 'reset'
}>(), {
  variant: 'secondary',
  size: 'medium',
  icon: undefined,
  type: 'button',
})
</script>

<template>
  <button
    :type="type"
    :class="['aima-button', `is-${variant}`, `is-${size}`]"
  >
    <AimaIcon
      v-if="icon"
      :name="icon"
      :size="size === 'small' ? 15 : 17"
    />
    <span><slot /></span>
  </button>
</template>

<style scoped>
.aima-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--aima-border-strong);
  border-radius: var(--aima-radius-control);
  color: var(--aima-text-secondary);
  background: var(--aima-surface);
  cursor: pointer;
  transition: border-color 120ms ease, color 120ms ease, background 120ms ease;
}

.is-medium {
  min-height: var(--aima-control-height-md);
  padding: 0 15px;
  font-size: var(--aima-font-size-control);
}

.is-small {
  min-height: var(--aima-button-height-sm);
  padding: 0 10px;
  font-size: var(--aima-font-size-body-small);
}

.is-primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
.is-outline { border-color: var(--aima-primary); color: var(--aima-primary); }
.is-text { min-height: auto; padding: 4px; border-color: transparent; color: var(--aima-primary); background: transparent; }
.aima-button:not(:disabled):hover { border-color: var(--aima-primary); color: var(--aima-primary); }
.is-primary:not(:disabled):hover { color: #fff; background: var(--aima-primary-hover); }
.aima-button:focus-visible { outline: 2px solid var(--aima-primary-soft-strong); outline-offset: 2px; }
.aima-button:disabled { color: var(--aima-text-disabled); background: var(--aima-surface-disabled); cursor: not-allowed; opacity: .72; }
</style>
