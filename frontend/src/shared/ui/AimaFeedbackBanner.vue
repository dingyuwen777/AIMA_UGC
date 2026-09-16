<script setup lang="ts">
import { computed } from 'vue'

import AimaIcon, { type AimaIconName } from './AimaIcon.vue'

const props = withDefaults(defineProps<{
  tone?: 'info' | 'success' | 'warning' | 'error'
  role?: 'status' | 'alert'
}>(), {
  tone: 'info',
  role: 'status',
})

const icon = computed<AimaIconName>(() => props.tone === 'error' ? 'warning' : props.tone)
</script>

<template>
  <div
    :class="['aima-feedback', `is-${tone}`]"
    :role="role"
  >
    <AimaIcon
      :name="icon"
      :size="16"
    />
    <div><slot /></div>
  </div>
</template>

<style scoped>
.aima-feedback {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border: 1px solid;
  border-radius: var(--aima-radius-lg);
  font-size: 12px;
  line-height: 18px;
}
.aima-feedback > div { min-width: 0; overflow-wrap: anywhere; }
.aima-feedback svg { flex: none; }
.is-info { border-color: var(--aima-color-info); color: var(--aima-color-info); background: var(--aima-color-info-bg); }
.is-success { border-color: var(--aima-color-success); color: var(--aima-color-success); background: var(--aima-color-success-bg); }
.is-warning { border-color: var(--aima-color-warning); color: var(--aima-color-warning); background: var(--aima-color-warning-bg); }
.is-error { border-color: var(--aima-color-error); color: var(--aima-color-error); background: var(--aima-color-error-bg); }
</style>
