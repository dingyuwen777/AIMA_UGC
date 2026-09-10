<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { listVehicleBrands, type BrandResponse } from '../generated/api/client'
import { apiErrorMessage, unwrapResponse } from './api/http'
import AimaButton from './ui/AimaButton.vue'
import AimaDialog from './ui/AimaDialog.vue'

const props = withDefaults(defineProps<{
  modelValue: string[]
  label?: string
  disabled?: boolean
  includeDeprecated?: boolean
  compact?: boolean
}>(), { label: '品牌', disabled: false, includeDeprecated: false, compact: false })

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const options = ref<BrandResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const open = ref(false)
const draft = ref<string[]>([])
const search = ref('')
const matching = computed(() => options.value.filter((item) => {
  const query = search.value.trim().toLocaleLowerCase()
  return !query || [item.display_name, item.code, ...(item.aliases ?? []).map((alias) => alias.text)]
    .some((text) => text.toLocaleLowerCase().includes(query))
}))
const selectedLabel = computed(() => {
  if (!props.modelValue.length) return '全部启用品牌及车型'
  if (props.modelValue.length === 1) {
    return options.value.find((item) => item.id === props.modelValue[0])?.display_name ?? '已选 1 个品牌'
  }
  return `已选 ${props.modelValue.length} 个品牌`
})

onMounted(load)

/** 读取完整品牌目录；创建新过滤条件时默认只暴露 active 品牌。 */
async function load(): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = null
  try {
    const items: BrandResponse[] = []
    let offset = 0
    while (true) {
      const response = unwrapResponse(await listVehicleBrands({
        status: props.includeDeprecated ? undefined : 'active',
        offset,
        limit: 200,
      }))
      if (!Array.isArray(response.items)) throw new Error('品牌目录响应无效，请稍后重试。')
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

function toggle(id: string): void {
  const next = new Set(props.modelValue)
  if (next.has(id)) next.delete(id)
  else if (next.size < 100) next.add(id)
  emit('update:modelValue', [...next])
}

function openPicker(): void {
  draft.value = [...props.modelValue]
  search.value = ''
  open.value = true
}

function toggleDraft(id: string): void {
  if (draft.value.includes(id)) draft.value = draft.value.filter((value) => value !== id)
  else if (draft.value.length < 100) draft.value.push(id)
}

function confirm(): void {
  emit('update:modelValue', [...draft.value])
  open.value = false
}

function roleLabel(role: BrandResponse['role']): string {
  return role === 'owned' ? '自有' : role === 'competitor' ? '竞品' : '其他'
}
</script>

<template>
  <div
    v-if="compact"
    class="brand-compact"
  >
    <span class="brand-label">{{ label }}</span>
    <button
      class="brand-trigger"
      type="button"
      :disabled="disabled"
      aria-label="选择品牌"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="openPicker"
    >
      <span>{{ selectedLabel }}</span><span aria-hidden="true">⌄</span>
    </button>
    <AimaDialog
      v-model="open"
      class="brand-picker"
      width="560px"
      label="选择品牌"
    >
      <template #header>
        <input
          v-model="search"
          class="brand-search"
          aria-label="搜索品牌"
          placeholder="搜索品牌名称、编码或识别词"
        >
      </template>
      <div class="brand-picker-body">
        <p v-if="loading">
          正在读取品牌目录…
        </p>
        <p
          v-else-if="error"
          class="brand-error"
        >
          {{ error }} <button
            type="button"
            @click="load"
          >
            重试
          </button>
        </p>
        <label
          v-for="item in matching"
          v-else
          :key="item.id"
        >
          <input
            type="checkbox"
            :checked="draft.includes(item.id)"
            @change="toggleDraft(item.id)"
          >
          <span><strong>{{ item.display_name }}</strong><small>{{ item.code }} · {{ roleLabel(item.role) }}</small></span>
        </label>
        <p v-if="!loading && !error && matching.length === 0">
          没有匹配品牌
        </p>
      </div>
      <template #footer>
        <div class="brand-picker-footer">
          <span>已选 {{ draft.length }} 个品牌</span><button
            type="button"
            @click="draft = []"
          >
            清空
          </button><AimaButton @click="open = false">
            取消
          </AimaButton><AimaButton
            variant="primary"
            @click="confirm"
          >
            确定
          </AimaButton>
        </div>
      </template>
    </AimaDialog>
  </div>
  <fieldset
    v-else
    class="brand-select"
    :disabled="disabled"
  >
    <legend>{{ label }}</legend>
    <p v-if="loading">
      正在读取品牌目录…
    </p>
    <div
      v-else-if="error"
      class="brand-select__error"
    >
      {{ error }}<button
        type="button"
        @click="load"
      >
        重试
      </button>
    </div>
    <div
      v-else
      class="brand-select__options"
    >
      <label
        v-for="item in options"
        :key="item.id"
      ><input
        type="checkbox"
        :checked="modelValue.includes(item.id)"
        @change="toggle(item.id)"
      ><span>{{ item.display_name }}</span><small>{{ roleLabel(item.role) }}</small></label>
      <p v-if="options.length === 0">
        当前没有可用品牌
      </p>
    </div>
  </fieldset>
</template>

<style scoped>
.brand-select { min-width: 0; margin: 0; padding: 10px 12px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); }
.brand-select legend { padding: 0 5px; color: var(--aima-text-muted); font-size: 11px; }
.brand-select p { margin: 0; color: var(--aima-text-disabled); font-size: 11px; }
.brand-select__error { display: flex; align-items: center; justify-content: space-between; color: var(--aima-danger); font-size: 11px; }
.brand-select__error button,.brand-picker-footer > button { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }
.brand-select__options { display: flex; max-height: 116px; flex-wrap: wrap; gap: 7px; overflow: auto; }
.brand-select__options label { display: inline-flex; min-height: 28px; align-items: center; gap: 5px; padding: 0 8px; border: 1px solid var(--aima-border); border-radius: 5px; color: var(--aima-text-secondary); cursor: pointer; font-size: 11px; }
.brand-select__options label:has(input:checked) { border-color: var(--aima-primary); color: var(--aima-primary); background: var(--aima-primary-soft); }
.brand-select__options input { width: 13px; height: 13px; margin: 0; accent-color: var(--aima-primary); }
.brand-select__options small { color: var(--aima-text-disabled); font-size: 9px; }
.brand-compact { min-width: 0; display: grid; gap: 6px; }
.brand-label { color: var(--aima-text-muted); font-size: 12px; font-weight: 700; }
.brand-trigger { display: flex; width: 100%; height: 40px; min-width: 0; align-items: center; justify-content: space-between; gap: 6px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; background: var(--aima-surface); color: var(--aima-text-muted); font-size: 13px; cursor: pointer; }
.brand-trigger > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brand-search { width: 100%; height: 36px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 6px; font: inherit; }
.brand-picker-body { display: grid; max-height: 420px; gap: 4px; padding: 10px 16px; overflow-y: auto; }
.brand-picker-body > label { display: flex; align-items: flex-start; gap: 8px; padding: 9px; border-bottom: 1px solid var(--aima-border); cursor: pointer; }
.brand-picker-body strong,.brand-picker-body small { display: block; }.brand-picker-body small { margin-top: 3px; color: var(--aima-text-muted); }
.brand-picker-body input { width: 16px; height: 16px; accent-color: var(--aima-primary); }
.brand-error { color: var(--aima-danger); }
.brand-picker-footer { display: flex; align-items: center; gap: 12px; }.brand-picker-footer > :deep(.aima-button:first-of-type) { margin-left: auto; }
</style>
