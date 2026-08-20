<script setup lang="ts">
import { ref, watch } from 'vue'

import type { DataExportResponse } from '../../../../../generated/api/client'
import { formatDateTime, formatNumber } from '../../../format'

const props = defineProps<{
  modelValue: boolean
  selectedCount: number
  pageCount: number
  items: DataExportResponse[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  submit: [scope: 'query' | 'selected' | 'page']
  refresh: []
  download: [item: DataExportResponse]
}>()
const scope = ref<'query' | 'selected' | 'page'>('selected')

watch(() => props.modelValue, (open) => {
  if (open) scope.value = props.selectedCount > 0 ? 'selected' : props.pageCount > 0 ? 'page' : 'query'
})

const statusLabels = {
  queued: '排队中',
  running: '导出中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="modal-layer"
    >
      <button
        class="backdrop"
        type="button"
        aria-label="关闭导出弹窗"
        @click="emit('update:modelValue', false)"
      /><section
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-title"
      >
        <header>
          <div>
            <h2 id="export-title">
              导出声音记录
            </h2><p>复用正式 Excel 导出链路，后台生成可下载 Artifact。</p>
          </div><button
            type="button"
            aria-label="关闭"
            @click="emit('update:modelValue', false)"
          >
            ×
          </button>
        </header><div class="body">
          <div class="choice-grid">
            <label :class="{ active: scope === 'selected', disabled: selectedCount === 0 }"><input
              v-model="scope"
              type="radio"
              value="selected"
              :disabled="selectedCount === 0"
            ><span><strong>已选内容</strong><small>{{ selectedCount }} 条</small></span></label><label :class="{ active: scope === 'page', disabled: pageCount === 0 }"><input
              v-model="scope"
              type="radio"
              value="page"
              :disabled="pageCount === 0"
            ><span><strong>当前页内容</strong><small>冻结已加载 {{ pageCount }} 条</small></span></label><label :class="{ active: scope === 'query' }"><input
              v-model="scope"
              type="radio"
              value="query"
            ><span><strong>全部查询结果</strong><small>按当前筛选条件冻结</small></span></label>
          </div><p class="analysis-note">
            未完成 AI 打标的内容不会被丢弃：仍会导出，AI 情感和标签列留空，并在结果统计中提示。
          </p><div class="records-title">
            <strong>最近导出记录</strong><button
              type="button"
              @click="emit('refresh')"
            >
              ↻ 刷新
            </button>
          </div><div class="records">
            <article
              v-for="item in items"
              :key="item.id"
            >
              <div>
                <strong>{{ item.filename || `声音广场导出 ${item.id.slice(0, 8)}` }}</strong><small>{{ formatDateTime(item.created_at) }} · {{ statusLabels[item.job.status] }} {{ item.job.progress }}%</small><span v-if="item.stats">内容 {{ formatNumber(item.stats.content_count) }} · 已打标 {{ formatNumber(item.stats.analyzed_count) }} · 未打标 {{ formatNumber(item.stats.unanalyzed_count) }}</span><span
                  v-if="item.job.error_code"
                  class="error"
                >{{ item.job.error_code }}</span>
              </div><button
                type="button"
                :disabled="item.job.status !== 'succeeded'"
                @click="emit('download', item)"
              >
                下载
              </button>
            </article><p
              v-if="items.length === 0"
              class="empty"
            >
              暂无导出记录。
            </p>
          </div>
        </div><footer>
          <button
            type="button"
            @click="emit('update:modelValue', false)"
          >
            关闭
          </button><button
            class="primary"
            type="button"
            :disabled="submitting"
            @click="emit('submit', scope)"
          >
            {{ submitting ? '正在创建…' : '创建 Excel 导出' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-layer { position: fixed; z-index: 130; inset: 0; display: grid; place-items: center; }
.backdrop { position: absolute; inset: 0; border: 0; background: rgb(25 32 45 / 48%); }
.modal { position: relative; width: 650px; overflow: hidden; border-radius: 11px; background: #fff; box-shadow: 0 22px 58px rgb(20 28 42 / 22%); }
header { display: flex; align-items: start; justify-content: space-between; padding: 21px 22px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; font-size: 19px; }
header p { margin: 6px 0 0; color: #7b8494; font-size: 12px; }
header button { border: 0; color: #7d8695; background: transparent; font-size: 25px; cursor: pointer; }
.body { padding: 20px 22px; }
.choice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.choice-grid label { display: flex; align-items: center; gap: 12px; padding: 13px; border: 1px solid #dfe3ea; border-radius: 7px; cursor: pointer; }
.choice-grid label.active { border-color: var(--aima-primary); background: var(--aima-primary-soft); }
.choice-grid label.disabled { opacity: .55; cursor: default; }
.choice-grid input { accent-color: var(--aima-primary); }
.choice-grid strong, .choice-grid small { display: block; }
.choice-grid small { margin-top: 4px; color: #7d8696; }
.analysis-note { padding: 10px; border: 1px solid #bcd5f5; border-radius: 6px; color: #39678f; background: #f2f7fd; font-size: 11px; line-height: 1.55; }
.records-title { display: flex; align-items: center; justify-content: space-between; margin: 18px 0 9px; }
.records-title button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }
.records { max-height: 250px; overflow-y: auto; border: 1px solid var(--aima-border); border-radius: 7px; }
.records article { display: flex; align-items: center; justify-content: space-between; padding: 12px; border-bottom: 1px solid #edf0f4; }
.records article:last-child { border-bottom: 0; }
.records strong, .records small, .records span { display: block; }
.records strong { color: #394355; font-size: 12px; }
.records small, .records span { margin-top: 4px; color: #7f8898; font-size: 10px; }
.records .error { color: #cf3440; }
.records button { height: 30px; padding: 0 12px; border: 1px solid var(--aima-primary); border-radius: 5px; color: var(--aima-primary); background: #fff; cursor: pointer; }
.records button:disabled { border-color: #d9dee7; color: #a1a8b4; cursor: default; }
.empty { padding: 24px; color: #969eac; text-align: center; }
footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 22px; border-top: 1px solid var(--aima-border); }
footer button { height: 38px; padding: 0 18px; border: 1px solid #d9dee7; border-radius: 6px; background: #fff; cursor: pointer; }
footer .primary { border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
footer button:disabled { opacity: .6; cursor: default; }
</style>
