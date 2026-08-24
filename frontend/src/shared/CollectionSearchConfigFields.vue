<script setup lang="ts">
import { computed } from 'vue'

import type {
  CollectionSearchCapabilityResponse,
  CollectionSearchConfig,
} from '../generated/api/client'
import {
  collectionSearchConfigFields,
  collectionSearchOptionLabel,
  type CollectionSearchConfigKey,
} from './collectionSearchConfig'

const props = defineProps<{
  capability: CollectionSearchCapabilityResponse
  modelValue: CollectionSearchConfig
  platformLabel: string
}>()
const emit = defineEmits<{
  'update:modelValue': [value: CollectionSearchConfig]
}>()

const fields = computed(() => collectionSearchConfigFields(props.capability))

function update(key: CollectionSearchConfigKey, event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  emit('update:modelValue', { ...props.modelValue, [key]: value || null })
}
</script>

<template>
  <div class="search-config-fields">
    <label
      v-for="field in fields"
      :key="field.key"
    >
      <span>{{ field.label }}</span>
      <select
        :aria-label="`${platformLabel}${field.label}`"
        :value="modelValue[field.key] ?? ''"
        @change="update(field.key, $event)"
      >
        <option value="">
          请选择
        </option>
        <option
          v-for="option in field.options"
          :key="option"
          :value="option"
        >
          {{ collectionSearchOptionLabel(option) }}
        </option>
      </select>
    </label>
  </div>
</template>

<style scoped>
.search-config-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
label { display: block; min-width: 0; }
label span { display: block; margin-bottom: 5px; color: #6f798c; font-size: 11px; }
select { width: 100%; height: 34px; padding: 0 8px; border: 1px solid #d9dee8; border-radius: 6px; color: #3c4557; background: #fff; font-size: 12px; }
</style>
