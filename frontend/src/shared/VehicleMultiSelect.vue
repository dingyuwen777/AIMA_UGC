<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { listVehicleModels, type VehicleModelResponse } from '../generated/api/client'
import { apiErrorMessage, unwrapResponse } from './api/http'

const props = withDefaults(defineProps<{
  modelValue: string[]
  label?: string
  disabled?: boolean
  includeDeprecated?: boolean
}>(), { label: '车型', disabled: false, includeDeprecated: false })

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const options = ref<VehicleModelResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selected = computed(() => new Set(props.modelValue))

onMounted(load)

/** 按后端 offset/limit 契约读取完整车型目录；默认只暴露 active 创建候选。 */
async function load(): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = null
  try {
    const items: VehicleModelResponse[] = []
    let offset = 0
    while (true) {
      const response = unwrapResponse(await listVehicleModels({
        status: props.includeDeprecated ? undefined : 'active',
        offset,
        limit: 200,
      }))
      if (!Array.isArray(response.items)) {
        throw new Error('车型目录响应无效，请稍后重试。')
      }
      items.push(...response.items)
      offset += response.items.length
      if (offset >= response.total || response.items.length === 0) break
    }
    options.value = items
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

/** 切换一个车型选择，只修改当前组件的选择集合。 */
function toggle(id: string): void {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  emit('update:modelValue', [...next])
}
</script>

<template>
  <fieldset
    class="vehicle-select"
    :disabled="disabled || loading"
  >
    <legend>{{ label }}</legend>
    <p v-if="loading">
      车型目录加载中…
    </p>
    <div
      v-else-if="error"
      class="vehicle-select__error"
      role="alert"
    >
      <span>{{ error }}</span>
      <button
        type="button"
        @click="load"
      >
        重试
      </button>
    </div>
    <div
      v-else
      class="vehicle-select__options"
    >
      <label
        v-for="item in options"
        :key="item.id"
      >
        <input
          type="checkbox"
          :checked="selected.has(item.id)"
          @change="toggle(item.id)"
        >
        <span>{{ item.display_name }}</span>
        <small>{{ item.code }}</small>
      </label>
      <em v-if="options.length === 0">暂无可选车型</em>
    </div>
  </fieldset>
</template>

<style scoped>
.vehicle-select { min-width: 0; margin: 0; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.vehicle-select legend { padding: 0 5px; color: var(--aima-text-muted); font-size: 11px; }
.vehicle-select p,
.vehicle-select em { margin: 0; color: var(--aima-text-disabled); font-size: 11px; font-style: normal; }
.vehicle-select__error { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--aima-danger); font-size: 11px; }
.vehicle-select__error button { flex: none; padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 11px; }
.vehicle-select__options { display: flex; max-height: 116px; flex-wrap: wrap; gap: 7px; overflow: auto; }
.vehicle-select__options label { display: inline-flex; min-height: 28px; align-items: center; gap: 5px; padding: 0 8px; border: 1px solid var(--aima-border); border-radius: 5px; color: var(--aima-text-secondary); cursor: pointer; font-size: 11px; }
.vehicle-select__options label:has(input:checked) { border-color: var(--aima-primary); color: var(--aima-primary); background: var(--aima-primary-soft); }
.vehicle-select__options input { width: 13px; height: 13px; margin: 0; accent-color: var(--aima-primary); }
.vehicle-select__options small { color: var(--aima-text-disabled); font-size: 9px; }
</style>
