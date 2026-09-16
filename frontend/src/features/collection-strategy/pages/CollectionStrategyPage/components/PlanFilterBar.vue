<script setup lang="ts">
import type { CollectionPlatform } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import { COLLECTION_PLATFORM_OPTIONS } from '../../../presentation'

const search = defineModel<string>('search', { required: true })
const enabled = defineModel<string>('enabled', { required: true })
const platform = defineModel<'' | CollectionPlatform>('platform', { required: true })
const emit = defineEmits<{ reset: []; query: [] }>()
</script>

<template>
  <section
    class="filters"
    aria-label="采集计划筛选"
  >
    <input
      v-model="search"
      class="filter-search"
      placeholder="搜索计划名称"
      aria-label="搜索计划名称"
    >
    <select
      v-model="enabled"
      class="filter-status"
      aria-label="采集计划状态"
    >
      <option value="">
        全部状态
      </option>
      <option value="true">
        已启用
      </option>
      <option value="false">
        已停用
      </option>
    </select>
    <select
      v-model="platform"
      class="filter-platform"
      aria-label="采集平台"
    >
      <option value="">
        全部平台
      </option>
      <option
        v-for="option in COLLECTION_PLATFORM_OPTIONS"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>
    <span class="filter-spacer" />
    <AimaButton @click="emit('reset')">
      重置
    </AimaButton>
    <AimaButton
      variant="primary"
      @click="emit('query')"
    >
      查询
    </AimaButton>
  </section>
</template>

<style scoped>
.filters {
  display: grid;
  width: min(100%, 1212px);
  min-height: 72px;
  grid-template-columns: minmax(260px, 420px) 120px 172px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 15px 16px;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: #fff;
}
.filters input,
.filters select {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #d9dee8;
  border-radius: 8px;
  color: var(--aima-text-secondary);
  background: #fff;
  font: inherit;
  font-size: 13px;
}
.filter-search { min-width: 0; }
.filter-spacer { min-width: 0; }
@media (min-width: 1500px) {
  .filters { grid-template-columns: minmax(420px, 722px) 120px 172px minmax(0, 1fr) auto auto; }
}
@media (max-width: 1260px) {
  .filters {
    grid-template-columns: minmax(240px, 1fr) 120px 150px auto auto;
  }
  .filter-spacer { display: none; }
}
@media (max-width: 900px) {
  .filters { grid-template-columns: minmax(220px, 1fr) 120px 150px; }
  .filters :deep(.aima-button) { width: 100%; }
}
</style>
