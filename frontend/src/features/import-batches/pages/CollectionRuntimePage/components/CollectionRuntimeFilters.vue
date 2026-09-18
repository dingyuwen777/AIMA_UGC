<script setup lang="ts">
import type {
  CollectionRuntimeRecordType,
  CollectionRuntimeStatus,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDateRange from '../../../../../shared/ui/AimaDateRange.vue'
import type { CollectionRuntimeTab } from '../../../store'
import { recordTypeLabels, runtimeStatusLabels } from '../../../format'

defineProps<{ activeTab: CollectionRuntimeTab }>()
const search = defineModel<string>('search', { required: true })
const status = defineModel<'' | CollectionRuntimeStatus>('status', { required: true })
const recordType = defineModel<'' | CollectionRuntimeRecordType>('recordType', { required: true })
const createdFrom = defineModel<string>('createdFrom', { required: true })
const createdTo = defineModel<string>('createdTo', { required: true })

defineEmits<{ search: []; reset: [] }>()
</script>

<template>
  <section
    class="filter-panel"
    aria-label="采集运行筛选"
  >
    <div class="filter-row">
      <label class="search-box">
        <input
          v-model="search"
          placeholder="搜索任务名称或来源文件"
        >
      </label>
      <AimaDateRange
        v-model:from="createdFrom"
        v-model:to="createdTo"
        class="runtime-date-range"
        label="创建时间范围"
      />
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
          v-show="activeTab === 'all' || (activeTab === 'excel' ? ['excel_import', 'data_import_campaign'].includes(value) : !['excel_import', 'data_import_campaign'].includes(value))"
          :key="value"
          :value="value"
        >
          {{ label }}
        </option>
      </select>
    </div>
    <div class="filter-actions">
      <span>按任务名称、创建时间、状态和类型筛选</span>
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
.filter-panel { padding: 16px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.filter-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-start; }
.search-box, select { height: 40px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.search-box { display: flex; min-width: 260px; flex: 1 1 280px; align-items: center; padding: 0 12px; }
.search-box input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--aima-text-secondary); background: transparent; font-size: 13px; line-height: 20px; }
.search-box input::placeholder { color: var(--aima-text-disabled); }
.runtime-date-range { width: 258px; flex: 0 0 258px; }
select { width: 132px; flex: 0 0 132px; min-width: 0; padding: 0 12px; color: var(--aima-text-secondary); font-size: 13px; line-height: 20px; }
.filter-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 16px; color: var(--aima-text-secondary); font-size: 12px; line-height: 18px; }
.filter-actions > div { display: flex; flex: none; gap: 12px; }
.filter-actions :deep(.aima-button.is-secondary) { min-width: 68px; }
.filter-actions :deep(.aima-button.is-primary) { min-width: 66px; }
@media (max-width: 1120px) {
  .filter-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .search-box,
  .runtime-date-range,
  select { box-sizing: border-box; width: 100%; min-width: 0; flex: none; }
}
@media (max-width: 860px) {
  .filter-actions { align-items: flex-end; flex-direction: column; }
  .filter-actions > span { align-self: flex-start; }
}
@media (max-width: 720px) {
  .filter-row { grid-template-columns: minmax(0, 1fr); }
}
</style>
