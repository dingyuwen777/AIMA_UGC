<script setup lang="ts">
import type {
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
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
      <label class="search-box">
        <AimaIcon
          name="search"
          :size="17"
        />
        <input
          v-model="search"
          placeholder="搜索批次名称、批次编号、运行编号"
        >
      </label>
      <div class="date-range">
        <input
          v-model="createdFrom"
          type="date"
          aria-label="开始日期"
        >
        <b>—</b>
        <input
          v-model="createdTo"
          type="date"
          aria-label="结束日期"
        >
      </div>
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
    </div>
    <div class="filter-actions">
      <span>时间按北京时间解释</span>
      <div>
        <AimaButton
          variant="secondary"
          size="small"
          @click="$emit('reset')"
        >
          重置
        </AimaButton>
        <AimaButton
          variant="primary"
          size="small"
          @click="$emit('search')"
        >
          查询
        </AimaButton>
      </div>
    </div>
  </section>
</template>

<style scoped>
.filter-panel { min-height: 126px; padding: 15px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius); background: var(--aima-surface); }
.filter-row { display: grid; grid-template-columns: minmax(260px, 326px) minmax(230px, 258px) repeat(3, minmax(118px, 132px)); gap: 12px; align-items: center; }
.search-box, select, .date-range { height: 40px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-control); background: var(--aima-surface); }
.search-box { display: flex; align-items: center; gap: 8px; padding: 0 12px; color: var(--aima-text-muted); }
.search-box input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--aima-text-secondary); background: transparent; font: inherit; font-size: 13px; }
.search-box input::placeholder { color: var(--aima-text-disabled); }
select { min-width: 0; padding: 0 12px; color: var(--aima-text-secondary); font-size: 13px; }
.date-range { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 4px; padding: 0 10px; color: var(--aima-text-muted); }
.date-range input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--aima-text-secondary); background: transparent; font-size: 12px; }
.date-range b { font-weight: 400; }
.filter-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 20px; color: var(--aima-text-disabled); font-size: 12px; line-height: 18px; }
.filter-actions > div { display: flex; gap: 8px; }
@media (max-width: 1180px) {
  .filter-row { grid-template-columns: minmax(240px, 1fr) minmax(230px, 1fr) repeat(3, minmax(110px, .6fr)); }
}
@media (max-width: 980px) {
  .filter-row { grid-template-columns: 1fr 1fr; }
  .filter-panel { min-height: 0; }
}
</style>
