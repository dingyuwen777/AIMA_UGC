<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AimaButton from '../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../shared/ui/AimaFeedbackBanner.vue'

interface LabelRow {
  id: number
  primary: string
  secondaries: string[]
}

const model = defineModel<string>({ required: true })
const emit = defineEmits<{ validity: [value: boolean] }>()
const rows = ref<LabelRow[]>([])
let nextId = 1
let syncingFromModel = false

const errors = computed(() => {
  const messages: string[] = []
  if (rows.value.length === 0) messages.push('至少需要一个一级标签。')
  if (rows.value.length > 100) messages.push('一级标签最多 100 个。')
  const primaryNames = rows.value.map((row) => row.primary.trim())
  if (primaryNames.some((value) => !value)) messages.push('一级标签不能为空。')
  if (new Set(primaryNames).size !== primaryNames.length) messages.push('一级标签不能重复。')

  const allSecondaries: string[] = []
  for (const row of rows.value) {
    const values = row.secondaries.map((value) => value.trim())
    if (values.length === 0 || values.some((value) => !value)) {
      messages.push(`“${row.primary.trim() || '未命名标签'}”至少需要一个非空二级标签。`)
      continue
    }
    if (new Set(values).size !== values.length) messages.push(`“${row.primary.trim()}”下存在重复二级标签。`)
    allSecondaries.push(...values)
  }
  if (new Set(allSecondaries).size !== allSecondaries.length) messages.push('二级标签不能跨一级标签重复。')

  const unknown = rows.value.find((row) => row.primary.trim() === '无法分类')
  if (!unknown || unknown.secondaries.length !== 1 || unknown.secondaries[0]?.trim() !== '无法判断') {
    messages.push('必须保留“无法分类 / 无法判断”作为兜底标签。')
  }
  return [...new Set(messages)]
})

const valid = computed(() => errors.value.length === 0)

watch(
  () => model.value,
  (value) => loadFromModel(value),
  { immediate: true },
)

watch(
  rows,
  () => {
    if (syncingFromModel) return
    emit('validity', valid.value)
    if (!valid.value) return
    const labels = Object.fromEntries(
      rows.value.map((row) => [
        row.primary.trim(),
        row.secondaries.map((value) => value.trim()),
      ]),
    )
    model.value = JSON.stringify(labels, null, 2)
  },
  { deep: true },
)

function loadFromModel(value: string): void {
  syncingFromModel = true
  try {
    const parsed = JSON.parse(value || '{}') as unknown
    const object = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {}
    const nextRows = Object.entries(object).flatMap(([primary, secondaries]) =>
      Array.isArray(secondaries) && secondaries.every((item) => typeof item === 'string')
        ? [{ id: nextId++, primary, secondaries: [...secondaries] as string[] }]
        : [],
    )
    if (!nextRows.some((row) => row.primary === '无法分类')) {
      nextRows.push({ id: nextId++, primary: '无法分类', secondaries: ['无法判断'] })
    }
    rows.value = nextRows
  } catch {
    rows.value = [{ id: nextId++, primary: '无法分类', secondaries: ['无法判断'] }]
  } finally {
    syncingFromModel = false
    emit('validity', valid.value)
    if (valid.value) {
      const labels = Object.fromEntries(
        rows.value.map((row) => [row.primary.trim(), row.secondaries.map((item) => item.trim())]),
      )
      const normalized = JSON.stringify(labels, null, 2)
      if (model.value !== normalized) model.value = normalized
    }
  }
}

function addPrimary(): void {
  if (rows.value.length >= 100) return
  rows.value.push({ id: nextId++, primary: '', secondaries: [''] })
}

function removePrimary(row: LabelRow): void {
  if (row.primary.trim() === '无法分类') return
  rows.value = rows.value.filter((item) => item.id !== row.id)
}

function addSecondary(row: LabelRow): void {
  row.secondaries.push('')
}

function removeSecondary(row: LabelRow, index: number): void {
  if (row.primary.trim() === '无法分类') return
  if (row.secondaries.length <= 1) return
  row.secondaries.splice(index, 1)
}
</script>

<template>
  <section class="labels-editor" aria-label="结构化标签规则">
    <header>
      <div>
        <strong>标签规则</strong>
        <p>直接维护一级标签和二级标签；系统会自动转换为正式结构化配置。</p>
      </div>
      <AimaButton size="small" :disabled="rows.length >= 100" @click="addPrimary">新增一级标签</AimaButton>
    </header>

    <div class="label-groups">
      <article v-for="row in rows" :key="row.id" class="label-group">
        <div class="primary-row">
          <label>
            <span>一级标签</span>
            <input
              v-model="row.primary"
              maxlength="200"
              :readonly="row.primary === '无法分类'"
              :aria-label="row.primary === '无法分类' ? '必需一级标签 无法分类' : '一级标签名称'"
            >
          </label>
          <AimaButton
            v-if="row.primary !== '无法分类'"
            variant="text"
            size="small"
            @click="removePrimary(row)"
          >移除一级标签</AimaButton>
        </div>
        <div class="secondary-list">
          <label v-for="(_, index) in row.secondaries" :key="`${row.id}-${index}`">
            <span>二级标签 {{ index + 1 }}</span>
            <span class="secondary-control">
              <input
                v-model="row.secondaries[index]"
                maxlength="200"
                :readonly="row.primary === '无法分类'"
              >
              <button
                v-if="row.primary !== '无法分类' && row.secondaries.length > 1"
                type="button"
                @click="removeSecondary(row, index)"
              >移除</button>
            </span>
          </label>
          <AimaButton
            v-if="row.primary !== '无法分类'"
            variant="text"
            size="small"
            @click="addSecondary(row)"
          >新增二级标签</AimaButton>
        </div>
      </article>
    </div>

    <AimaFeedbackBanner v-if="errors.length" tone="error" role="alert">
      <strong>标签规则还不能保存</strong>
      <span>{{ errors.join('；') }}</span>
    </AimaFeedbackBanner>
    <AimaFeedbackBanner v-else tone="info">
      “无法分类 / 无法判断”为系统必需兜底项，不允许删除或改名。
    </AimaFeedbackBanner>
  </section>
</template>

<style scoped>
.labels-editor { display: grid; gap: 10px; padding: 12px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-control); background: #fbfcfe; }
.labels-editor > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.labels-editor header strong { color: var(--aima-text); font-size: 12px; }.labels-editor header p { margin: 3px 0 0; color: var(--aima-text-muted); font-size: 10px; line-height: 15px; }
.label-groups { display: grid; gap: 8px; }.label-group { display: grid; gap: 8px; padding: 10px; border: 1px solid var(--aima-border); border-radius: 7px; background: #fff; }.primary-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; align-items: end; }.label-group label { display: grid; gap: 4px; color: var(--aima-text-muted); font-size: 10px; }.label-group input { width: 100%; height: 34px; padding: 0 9px; border: 1px solid var(--aima-border-strong); border-radius: 5px; color: var(--aima-text-secondary); background: #fff; font-size: 11px; }.label-group input:read-only { background: #f5f7fa; color: var(--aima-text-muted); }
.secondary-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 7px; }.secondary-control { display: flex; gap: 5px; }.secondary-control button { flex: none; border: 0; color: var(--aima-danger); background: transparent; cursor: pointer; font-size: 10px; }.secondary-list > :deep(.aima-button) { align-self: end; justify-self: start; }
@media (max-width: 900px) { .secondary-list { grid-template-columns: 1fr; } }
</style>