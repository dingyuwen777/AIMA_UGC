<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AimaDialog from './ui/AimaDialog.vue'

import { listVehicleModels, type VehicleModelResponse } from '../generated/api/client'
import { apiErrorMessage, unwrapResponse } from './api/http'
import AimaButton from './ui/AimaButton.vue'

const props = withDefaults(defineProps<{
  modelValue: string[]
  label?: string
  disabled?: boolean
  includeDeprecated?: boolean
  compact?: boolean
}>(), { label: '车型', disabled: false, includeDeprecated: false, compact: false })

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const options = ref<VehicleModelResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selected = computed(() => new Set(props.modelValue))
const open = ref(false)
const draft = ref<string[]>([])
const search = ref('')
const series = ref<string | null | undefined>(undefined)
const groups = computed(() => [...new Set(options.value.map((item) => item.series_name ?? null))])
const matching = computed(() => options.value.filter((item) => {
  const query = search.value.trim().toLocaleLowerCase()
  return (series.value === undefined || (item.series_name ?? null) === series.value) &&
    (!query || [item.display_name, item.code, item.series_name, ...(item.aliases ?? []).map((alias) => alias.text)].some((text) => text?.toLocaleLowerCase().includes(query)))
}))
const selectedLabel = computed(() => {
  if (!props.modelValue.length) return '全部车型'
  if (props.modelValue.length === 1) return options.value.find((item) => item.id === props.modelValue[0])?.display_name ?? '已选 1 项'
  return `已选 ${props.modelValue.length} 项`
})

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

/** 弹窗持有临时选择，只有确认后才修改业务筛选。 */
function openPicker(): void {
  draft.value = [...props.modelValue]
  search.value = ''
  series.value = undefined
  open.value = true
}

/** 当前筛选最多接收 100 个车型 ID，保持与服务端 Contract 一致。 */
function toggleDraft(id: string): void {
  if (draft.value.includes(id)) draft.value = draft.value.filter((value) => value !== id)
  else if (draft.value.length < 100) draft.value.push(id)
}

/** 全选只作用于当前系列及搜索结果，不移除其他系列的既有选择。 */
function selectMatching(): void {
  draft.value = [...new Set([...draft.value, ...matching.value.map((item) => item.id)])].slice(0, 100)
}

/** 确认本次临时选择并关闭弹窗。 */
function confirm(): void {
  emit('update:modelValue', [...draft.value])
  open.value = false
}
</script>

<template>
  <div
    v-if="compact"
    class="vehicle-compact"
  >
    <span class="vehicle-label">{{ label }}</span>
    <button
      class="vehicle-trigger"
      type="button"
      :disabled="disabled"
      aria-label="选择车型"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="openPicker"
    >
      <span>{{ selectedLabel }}</span><span aria-hidden="true">⌄</span>
    </button>
    <AimaDialog
      v-model="open"
      class="vehicle-picker"
      width="620px"
      label="选择车型"
    >
      <template #header>
        <input
          v-model="search"
          class="vehicle-search"
          aria-label="搜索车型"
          placeholder="搜索型号…"
        >
      </template>
      <div
        v-if="loading"
        class="vehicle-picker-state"
        role="status"
      >
        车型目录加载中…
      </div>
      <div
        v-else-if="error"
        class="vehicle-picker-state"
        role="alert"
      >
        <span>{{ error }}</span><AimaButton @click="load">
          重试
        </AimaButton>
      </div>
      <div
        v-else
        class="vehicle-picker-body"
      >
        <nav
          class="vehicle-groups"
          aria-label="车型系列"
        >
          <button
            type="button"
            :class="{ active: series === undefined }"
            @click="series = undefined"
          >
            全部系列 <span>›</span>
          </button>
          <button
            v-for="group in groups"
            :key="group ?? '__ungrouped'"
            type="button"
            :class="{ active: series === group }"
            @click="series = group"
          >
            {{ group ?? '未分组' }} <span>›</span>
          </button>
        </nav>
        <section class="vehicle-matches">
          <h3>{{ series === undefined ? '全部系列' : series ?? '未分组' }} | 已选 {{ draft.length }} 项</h3>
          <div class="vehicle-match-list">
            <label
              v-for="item in matching"
              :key="item.id"
              :title="item.display_name"
            ><input
              type="checkbox"
              :checked="draft.includes(item.id)"
              :disabled="!draft.includes(item.id) && draft.length >= 100"
              @change="toggleDraft(item.id)"
            ><span>{{ item.display_name }}</span></label>
            <p v-if="!matching.length">
              {{ options.length ? '暂无匹配车型' : '暂无可选车型' }}
            </p>
          </div>
        </section>
      </div>
      <template #footer>
        <div class="vehicle-picker-footer">
          <span>共 {{ options.length }} 项</span><button
            type="button"
            :disabled="loading || Boolean(error)"
            @click="selectMatching"
          >
            全选
          </button><button
            type="button"
            @click="draft = []"
          >
            清空
          </button><span
            v-if="draft.length >= 100"
            class="selection-limit"
          >最多选择 100 项</span><AimaButton
            size="small"
            @click="open = false"
          >
            取消
          </AimaButton><AimaButton
            variant="primary"
            size="small"
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

<style>
.vehicle-compact { min-width: 0; display: grid; gap: 6px; }
.vehicle-label { color: var(--aima-text-muted); font-size: 12px; font-weight: 700; }
.vehicle-trigger { display: flex; width: 100%; height: 40px; min-width: 0; align-items: center; justify-content: space-between; gap: 6px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 8px; background: var(--aima-surface); color: var(--aima-text-muted); font-size: 13px; cursor: pointer; }
.vehicle-trigger > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vehicle-picker.aima-dialog { max-width: calc(100vw - 32px); padding: 0; border-radius: 12px; overflow: hidden; --el-color-primary: var(--aima-primary); }
.vehicle-picker .aima-dialog-header { padding: 16px; margin: 0; border-bottom: 1px solid var(--aima-border); }
.vehicle-search { width: 100%; height: 34px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: 6px; font: inherit; font-size: 13px; }
.vehicle-picker .aima-dialog-body { padding: 0; }
.vehicle-picker-body { display: grid; height: min(352px, 55vh); grid-template-columns: 168px minmax(0, 1fr); }
.vehicle-groups { overflow-y: auto; padding: 0 14px; border-right: 1px solid var(--aima-border); }
.vehicle-groups button { display: flex; width: 100%; min-height: 42px; align-items: center; justify-content: space-between; gap: 6px; padding: 10px 0; border: 0; border-bottom: 1px solid var(--aima-primary-soft); color: var(--aima-text); background: #fff; text-align: left; font-size: 13px; font-weight: 600; cursor: pointer; }
.vehicle-groups button.active, .vehicle-groups button span { color: var(--aima-primary); }
.vehicle-matches { display: flex; min-width: 0; min-height: 0; flex-direction: column; }
.vehicle-matches h3 { margin: 0; padding: 12px 20px; border-bottom: 1px solid var(--aima-border); color: var(--aima-text-muted); font-size: 13px; }
.vehicle-match-list { display: grid; min-height: 0; grid-template-columns: repeat(3, minmax(0, 1fr)); align-content: start; gap: 4px; padding: 8px; overflow-y: auto; }
.vehicle-match-list label { display: flex; min-width: 0; align-items: flex-start; gap: 6px; padding: 6px; color: var(--aima-text); font-size: 12px; line-height: 18px; cursor: pointer; overflow-wrap: anywhere; }
.vehicle-match-list input { flex: none; width: 16px; height: 16px; margin: 1px 0 0; accent-color: var(--aima-primary); }
.vehicle-match-list p { grid-column: 1 / -1; text-align: center; color: var(--aima-text-muted); }
.vehicle-picker-state { display: grid; min-height: 200px; place-content: center; gap: 12px; text-align: center; }
.vehicle-picker .aima-dialog-footer { padding: 10px 16px; background: var(--aima-color-bg-table-header); border-top: 1px solid var(--aima-border); }
.vehicle-picker-footer { display: flex; align-items: center; gap: 16px; color: var(--aima-text-muted); font-size: 12px; }
.vehicle-picker-footer > button:not(.aima-button) { padding: 0; border: 0; background: transparent; color: var(--aima-primary); font-size: 12px; cursor: pointer; }
.vehicle-picker-footer .aima-button:first-of-type, .vehicle-picker-footer .aima-button:nth-last-child(2) { margin-left: auto; }
.selection-limit { color: var(--aima-warning); }
@media (max-width: 620px) { .vehicle-picker-body { grid-template-columns: 120px minmax(0, 1fr); } .vehicle-match-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } .vehicle-picker-footer { gap: 8px; flex-wrap: wrap; } }
</style>
