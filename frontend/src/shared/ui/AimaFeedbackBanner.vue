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
      :size="17"
    />
    <div><slot /></div>
  </div>
</template>

<style scoped>
.aima-feedback { display: flex; align-items: flex-start; gap: 9px; padding: 11px 13px; border: 1px solid; border-radius: var(--aima-radius-control); font-size: 12px; line-height: 18px; }
.aima-feedback svg { flex: none; margin-top: 1px; }
.is-info { border-color: #1677ff; color: #1768c8; background: #eef7ff; }
.is-success { border-color: #afe2c8; color: #14834f; background: #effaf4; }
.is-warning { border-color: #ffd29f; color: #a85709; background: #fff8ef; }
.is-error { border-color: #ffc4ca; color: #b4232d; background: #fff5f6; }
</style>
