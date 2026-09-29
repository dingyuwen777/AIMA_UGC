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

/** 从正式 JSON 结构恢复可编辑行，不向当前 Scheme 注入 Prompt 未声明的标签。 */
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
    rows.value = nextRows
  } catch {
    rows.value = []
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

/** 新增一级标签。 */
function addPrimary(): void {
  if (rows.value.length >= 100) return
  rows.value.push({ id: nextId++, primary: '', secondaries: [''] })
}

/** 移除一级标签。 */
function removePrimary(row: LabelRow): void {
  rows.value = rows.value.filter((item) => item.id !== row.id)
}

/** 在指定一级标签下新增二级标签。 */
function addSecondary(row: LabelRow): void {
  row.secondaries.push('')
}

/** 移除二级标签，但始终为一级标签保留至少一项。 */
function removeSecondary(row: LabelRow, index: number): void {
  if (row.secondaries.length <= 1) return
  row.secondaries.splice(index, 1)
}
</script>

<template>
  <section
    class="labels-editor"
    aria-label="结构化标签规则"
  >
    <strong class="labels-title">标签规则</strong>

    <div class="label-groups">
      <article
        v-for="row in rows"
        :key="row.id"
        class="label-group"
      >
        <label>
          <span>一级标签</span>
          <input
            v-model="row.primary"
            maxlength="200"
            aria-label="一级标签名称"
          >
        </label>

        <div class="secondary-list">
          <label
            v-for="(_, index) in row.secondaries"
            :key="`${row.id}-${index}`"
          >
            <span>{{ index === 0 ? '二级标签' : `二级标签 ${index + 1}` }}</span>
            <span class="secondary-control">
              <input
                v-model="row.secondaries[index]"
                maxlength="200"
                :aria-label="`二级标签 ${index + 1}`"
              >
              <button
                v-if="row.secondaries.length > 1"
                type="button"
                @click="removeSecondary(row, index)"
              >
                移除
              </button>
            </span>
          </label>
        </div>

        <div class="label-actions">
          <AimaButton
            size="small"
            @click="addSecondary(row)"
          >
            新增二级标签
          </AimaButton>
          <AimaButton
            size="small"
            @click="removePrimary(row)"
          >
            移除一级标签
          </AimaButton>
        </div>
      </article>
    </div>

    <AimaButton
      size="small"
      :disabled="rows.length >= 100"
      @click="addPrimary"
    >
      新增一级标签
    </AimaButton>

    <AimaFeedbackBanner
      v-if="errors.length"
      tone="error"
      role="alert"
    >
      <strong>标签规则还不能保存</strong>
      <span>{{ errors.join('；') }}</span>
    </AimaFeedbackBanner>
  </section>
</template>

<style scoped>
.labels-editor {
  display: grid;
  gap: 12px;
}
.labels-title {
  color: var(--aima-text-tertiary);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}
.label-groups {
  display: grid;
  gap: 12px;
}
.label-group {
  display: grid;
  gap: 8px;
  padding: 12px;
  background: #fff;
}
.label-group label {
  display: grid;
  gap: 6px;
  color: var(--aima-text-tertiary);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}
.label-group input {
  width: 100%;
  height: 40px;
  box-sizing: border-box;
  padding: 0 12px;
  border: 1px solid var(--aima-border-strong);
  border-radius: 8px;
  color: var(--aima-text);
  background: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 400;
}
.label-group input:read-only {
  cursor: not-allowed;
  color: var(--aima-text-disabled);
  background: var(--aima-color-bg-disabled, #f2f5f7);
}
.secondary-list {
  display: grid;
  gap: 8px;
}
.secondary-control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.secondary-control button {
  flex: none;
  border: 0;
  color: var(--aima-primary);
  background: transparent;
  cursor: pointer;
  font-size: 11px;
}
.label-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
