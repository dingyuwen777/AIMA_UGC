<script setup lang="ts">
import type {
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
} from '../../../../../generated/api/client'
import type { CollectionRuntimeTab } from '../../../store'
import { recordTypeLabels, runtimeStatusLabels } from '../../../format'

defineProps<{ activeTab: CollectionRuntimeTab }>()
const search = defineModel<string>('search', { required: true })
const status = defineModel<'' | CollectionRuntimeStatus>('status', { required: true })
const recordType = defineModel<'' | CollectionRuntimeRecordType>('recordType', { required: true })
const stage = defineModel<string>('stage', { required: true })
const createdFrom = defineModel<string>('createdFrom', { required: true })
const createdTo = defineModel<string>('createdTo', { required: true })

defineEmits<{ search: []; reset: [] }>()

const stageOptions = [
  ['queued', '等待处理'],
  ['reading', 'Excel 读取'],
  ['mapping', '字段映射'],
  ['filtering', '相关性过滤'],
  ['deduplicating', '去重'],
  ['ingesting', '内容入库'],
  ['content_discovery', 'TikHub 采集中'],
  ['content_enrichment', '内容补采'],
] as const
</script>

<template>
  <section
    class="filter-panel"
    aria-label="采集运行筛选"
  >
    <div class="filter-row">
      <label class="search-box"><span>⌕</span><input
        v-model="search"
        placeholder="搜索批次名称、Batch ID、Run ID"
      ></label>
      <select
        v-model="status"
        aria-label="状态"
      >
        <option value="">
          全部状态
        </option>
        <option
          v-for="(label, value) in runtimeStatusLabels"
          :key="value"
          :value="value"
        >
          {{ label }}
        </option>
      </select>
      <select
        v-model="recordType"
        aria-label="类型"
      >
        <option value="">
          全部类型
        </option>
        <option
          v-for="(label, value) in recordTypeLabels"
          v-show="activeTab === 'all' || (activeTab === 'excel' ? value === 'excel_import' : value !== 'excel_import')"
          :key="value"
          :value="value"
        >
          {{ label }}
        </option>
      </select>
      <select
        v-model="stage"
        aria-label="处理阶段"
      >
        <option value="">
          全部阶段
        </option>
        <option
          v-for="option in stageOptions"
          :key="option[0]"
          :value="option[0]"
        >
          {{ option[1] }}
        </option>
      </select>
      <div class="date-range">
        <span>▣</span><input
          v-model="createdFrom"
          type="date"
          aria-label="开始日期"
        ><b>—</b><input
          v-model="createdTo"
          type="date"
          aria-label="结束日期"
        >
      </div>
    </div>
    <div class="filter-actions">
      <span>筛选时间按北京时间解释；列表使用签名 Cursor 分页。</span>
      <div>
        <button
          type="button"
          @click="$emit('reset')"
        >
          重置
        </button><button
          class="primary"
          type="button"
          @click="$emit('search')"
        >
          查询
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.filter-panel { padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: #fff; }
.filter-row { display: grid; grid-template-columns: minmax(240px, 1.4fr) 130px 145px 145px minmax(290px, 1.2fr); gap: 10px; }
.search-box, select, .date-range { height: 42px; border: 1px solid #d9dee8; border-radius: 7px; background: #fff; }
.search-box { display: flex; align-items: center; gap: 8px; padding: 0 12px; }
.search-box span { color: #7d8799; font-size: 20px; }
.search-box input { width: 100%; border: 0; outline: 0; }
select { min-width: 0; padding: 0 10px; color: #3c4557; }
.date-range { display: flex; align-items: center; gap: 6px; padding: 0 10px; color: #667085; }
.date-range input { min-width: 110px; border: 0; outline: 0; color: #3c4557; }
.date-range b { font-weight: 400; }
.filter-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; color: #8a93a4; font-size: 12px; }
.filter-actions button { height: 36px; padding: 0 22px; border: 1px solid #d8dde6; border-radius: 7px; color: #313a4c; background: #fff; cursor: pointer; }
.filter-actions .primary { margin-left: 10px; border-color: var(--aima-primary); color: #fff; background: var(--aima-primary); }
</style>
