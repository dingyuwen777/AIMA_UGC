<script setup lang="ts">
import type { ImportBatchStatus, ImportStage } from '../../../../../generated/api/client'
import { stageLabels, statusLabels } from '../../../format'

const identifier = defineModel<string>('identifier', { required: true })
const status = defineModel<'' | ImportBatchStatus>('status', { required: true })
const stage = defineModel<'' | ImportStage>('stage', { required: true })
const createdFrom = defineModel<string>('createdFrom', { required: true })
const createdTo = defineModel<string>('createdTo', { required: true })

defineEmits<{ search: []; reset: [] }>()
</script>

<template>
  <section
    class="filter-panel"
    aria-label="批次筛选"
  >
    <div class="filter-row">
      <label class="search-box"><span>⌕</span><input
        v-model="identifier"
        placeholder="输入完整 Batch ID 或 Job ID"
      ></label>
      <select
        v-model="status"
        aria-label="状态"
      >
        <option value="">
          全部状态
        </option>
        <option
          v-for="(label, value) in statusLabels"
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
          v-for="(label, value) in stageLabels"
          :key="value"
          :value="value"
        >
          {{ label }}
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
      <div class="active-hint">
        筛选使用北京时间，ID 为精确匹配。
      </div>
      <div>
        <button
          class="button button--secondary"
          type="button"
          @click="$emit('reset')"
        >
          条件重置
        </button><button
          class="button button--primary"
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
.filter-row { display: grid; grid-template-columns: minmax(240px, 1.4fr) 150px 160px minmax(330px, 1.25fr); gap: 12px; }
.search-box, select, .date-range { height: 42px; border: 1px solid #d9dee8; border-radius: 7px; background: #fff; }
.search-box { display: flex; align-items: center; gap: 8px; padding: 0 12px; }
.search-box span { color: #7d8799; font-size: 20px; }
.search-box input { width: 100%; border: 0; outline: 0; }
select { padding: 0 12px; color: #3c4557; }
.date-range { display: flex; align-items: center; gap: 7px; padding: 0 12px; color: #667085; }
.date-range input { min-width: 125px; border: 0; outline: 0; color: #3c4557; }
.date-range b { font-weight: 400; }
.filter-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 15px; }
.active-hint { color: #8a93a4; font-size: 12px; }
.button { height: 38px; padding: 0 23px; border-radius: 7px; cursor: pointer; }
.button--secondary { margin-right: 10px; border: 1px solid #d8dde6; color: #313a4c; background: #fff; }
.button--primary { border: 1px solid var(--aima-primary); color: #fff; background: var(--aima-primary); box-shadow: 0 5px 12px rgb(245 0 87 / 18%); }
</style>
