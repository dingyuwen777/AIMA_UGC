<script setup lang="ts">
import { ref, watch } from 'vue'

import type { KeywordPackSummaryResponse } from '../../../../../generated/api/client'

const props = defineProps<{
  modelValue: boolean
  uploading: boolean
  keywordPacks: KeywordPackSummaryResponse[]
  loadingKeywordPacks: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [file: File, keywordPackIds: string[]]
}>()
const selectedFile = ref<File | null>(null)
const selectedPackIds = ref<string[]>([])
const validationError = ref<string | null>(null)
const maxBytes = 500 * 1024 * 1024
const maxKeywordPacks = 20

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      selectedFile.value = null
      selectedPackIds.value = []
      validationError.value = null
    }
  },
)

function selectFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  validationError.value = null
  if (file && !file.name.toLocaleLowerCase().endsWith('.xlsx')) {
    validationError.value = '只支持 .xlsx 文件。'
    selectedFile.value = null
    return
  }
  if (file && file.size > maxBytes) {
    validationError.value = 'Excel 文件不能超过 500 MiB。'
    selectedFile.value = null
    return
  }
  selectedFile.value = file
}

function togglePack(packId: string): void {
  if (selectedPackIds.value.includes(packId)) {
    selectedPackIds.value = selectedPackIds.value.filter((value) => value !== packId)
    validationError.value = null
    return
  }
  if (selectedPackIds.value.length >= maxKeywordPacks) {
    validationError.value = `一次最多选择 ${maxKeywordPacks} 个关键词包。`
    return
  }
  selectedPackIds.value = [...selectedPackIds.value, packId]
  validationError.value = null
}

function submit(): void {
  if (!selectedFile.value) {
    validationError.value = '请先选择一个 .xlsx 文件。'
    return
  }
  if (selectedPackIds.value.length === 0) {
    validationError.value = '请至少选择一个关键词包。'
    return
  }
  emit('submit', selectedFile.value, selectedPackIds.value)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="dialog-layer"
      role="presentation"
      @click.self="!uploading && emit('update:modelValue', false)"
    >
      <section
        class="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
      >
        <header>
          <h2 id="upload-title">
            导入 Excel
          </h2><button
            type="button"
            :disabled="uploading"
            aria-label="关闭导入窗口"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header>
        <div class="dialog-body">
          <p class="description">
            选择一个或多个关键词包（最多 20 个）。系统会冻结词包版本，将有效关键词合并去重；标题或正文命中任意关键词即可进入后续去重与入库。
          </p>
          <label class="drop-zone">
            <input
              type="file"
              accept=".xlsx"
              :disabled="uploading"
              @change="selectFile"
            >
            <span class="upload-icon">⇧</span><strong>{{ selectedFile?.name || '选择 Excel 文件' }}</strong>
            <small>单个 .xlsx 最大 500 MiB；实际导入在 Worker 中继续执行。</small>
          </label>
          <section class="pack-section">
            <strong>关键词包（可多选，已选 {{ selectedPackIds.length }}/{{ maxKeywordPacks }}）</strong>
            <p
              v-if="loadingKeywordPacks"
              class="pack-state"
            >
              正在加载词包…
            </p>
            <p
              v-else-if="keywordPacks.length === 0"
              class="pack-state"
            >
              当前没有可用的已启用词包。
            </p>
            <div
              v-else
              class="pack-list"
            >
              <label
                v-for="pack in keywordPacks"
                :key="pack.id"
                class="pack-item"
              >
                <input
                  type="checkbox"
                  :checked="selectedPackIds.includes(pack.id)"
                  :disabled="uploading"
                  @change="togglePack(pack.id)"
                >
                <span><b>{{ pack.name }}</b><small>{{ pack.keyword_count }} 个关键词 · v{{ pack.version }}</small></span>
              </label>
            </div>
          </section>
          <p
            v-if="validationError"
            class="validation-error"
          >
            {{ validationError }}
          </p>
        </div>
        <footer>
          <button
            class="dialog-button"
            type="button"
            :disabled="uploading"
            @click="emit('update:modelValue', false)"
          >
            取消
          </button>
          <button
            class="dialog-button dialog-button--primary"
            type="button"
            :disabled="uploading || loadingKeywordPacks || keywordPacks.length === 0"
            @click="submit"
          >
            {{ uploading ? '正在创建…' : '开始导入' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-layer { position: fixed; inset: 0; z-index: 120; display: grid; place-items: center; background: rgb(22 29 43 / 45%); }
.dialog { width: 560px; max-height: 86vh; overflow: hidden; border-radius: 10px; background: #fff; box-shadow: 0 18px 60px rgb(22 29 43 / 20%); }
.dialog header { display: flex; height: 58px; align-items: center; justify-content: space-between; padding: 0 22px; border-bottom: 1px solid var(--aima-border); }
.dialog h2 { margin: 0; font-size: 18px; }
.dialog header button { border: 0; color: #596275; background: transparent; cursor: pointer; font-size: 24px; }
.dialog-body { max-height: calc(86vh - 130px); overflow: auto; padding: 22px; }
.dialog footer { padding: 14px 22px; border-top: 1px solid var(--aima-border); text-align: right; }
.description { margin-top: 0; color: #657087; font-size: 13px; line-height: 1.7; }
.drop-zone { display: flex; min-height: 150px; align-items: center; flex-direction: column; justify-content: center; border: 1px dashed #ff7fac; border-radius: 9px; background: #fff9fb; cursor: pointer; }
.drop-zone input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.upload-icon { display: grid; width: 42px; height: 42px; margin-bottom: 12px; place-items: center; border-radius: 50%; color: #fff; background: var(--aima-primary); font-size: 23px; }
.drop-zone strong { max-width: 450px; overflow: hidden; color: #313a4c; text-overflow: ellipsis; white-space: nowrap; }
.drop-zone small { margin-top: 8px; color: #8992a3; }
.pack-section { margin-top: 18px; }
.pack-section > strong { color: #313a4c; font-size: 14px; }
.pack-state { color: #8992a3; font-size: 13px; }
.pack-list { display: grid; gap: 8px; max-height: 210px; margin-top: 10px; overflow: auto; }
.pack-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border: 1px solid #e1e5ec; border-radius: 7px; cursor: pointer; }
.pack-item span { display: grid; gap: 3px; }
.pack-item b { color: #313a4c; font-size: 13px; }
.pack-item small { color: #8992a3; font-size: 12px; }
.validation-error { color: var(--aima-danger); font-size: 13px; }
.dialog-button { height: 38px; padding: 0 22px; border: 1px solid #d9dee8; border-radius: 6px; background: #fff; cursor: pointer; }
.dialog-button--primary { margin-left: 10px; border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
.dialog-button:disabled { cursor: wait; opacity: .65; }
</style>
