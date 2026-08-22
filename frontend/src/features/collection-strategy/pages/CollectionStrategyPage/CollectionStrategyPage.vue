<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { CollectionPlanCreateRequest, CollectionPlanResponse } from '../../../../generated/api/client'
import AppShell from '../../../../app/layouts/AppShell.vue'
import { useCollectionStrategyStore } from '../../store'
import KeywordPackCreateDialog from './components/KeywordPackCreateDialog.vue'
import KeywordPackPanel from './components/KeywordPackPanel.vue'
import PlanCreateDrawer from './components/PlanCreateDrawer.vue'
import PlanDetailDrawer from './components/PlanDetailDrawer.vue'
import PlanPanel from './components/PlanPanel.vue'
import RelevancePanel from './components/RelevancePanel.vue'
import StrategyKpiCards from './components/StrategyKpiCards.vue'

const store = useCollectionStrategyStore()
const packDialogOpen = ref(false)
const planDrawerOpen = ref(false)
const planDetailOpen = computed({
  get: () => store.selectedPlan !== null,
  set: (value: boolean) => { if (!value) store.selectedPlan = null },
})
const notice = ref<string | null>(null)
const relevancePackName = computed(
  () => store.packs.find((pack) => pack.id === store.relevance?.keyword_pack_id)?.name ?? '',
)
const providers = computed(() => store.capabilities?.provider_configs ?? [])

onMounted(() => store.refresh())

async function savePack(name: string, description: string, keywords: string[]): Promise<void> {
  if (await store.savePack(name, description, keywords)) {
    packDialogOpen.value = false
    showNotice('Discovery 词包已保存。')
  }
}

async function addKeyword(packId: string, text: string): Promise<void> {
  if (await store.addKeyword(packId, text)) showNotice('关键词已加入词包。')
}

async function saveRelevance(packId: string): Promise<void> {
  if (await store.saveRelevance(packId)) showNotice('系统全局 Relevance 已更新。')
}

async function savePlan(request: CollectionPlanCreateRequest): Promise<void> {
  if (await store.savePlan(request)) {
    planDrawerOpen.value = false
    showNotice('周期采集计划已保存，将由 Scheduler 执行。')
  }
}

function openPlan(plan: CollectionPlanResponse): void {
  store.selectedPlan = plan
}

function showNotice(message: string): void {
  notice.value = message
  window.setTimeout(() => { if (notice.value === message) notice.value = null }, 2600)
}
</script>

<template>
  <AppShell section-title="采集策略">
    <div class="page-header">
      <div><h1>采集策略</h1><p>统一管理 Discovery 词包、全局相关性与周期采集计划</p></div>
      <div class="actions">
        <button
          type="button"
          @click="store.refresh()"
        >
          ↻&nbsp; 刷新数据
        </button><button
          type="button"
          class="outline"
          @click="packDialogOpen = true"
        >
          ＋&nbsp; 新建词包
        </button><button
          type="button"
          class="primary"
          @click="planDrawerOpen = true"
        >
          ＋&nbsp; 新建采集计划
        </button>
      </div>
    </div>

    <StrategyKpiCards
      :pack-count="store.packTotal"
      :relevance="store.relevance"
      :relevance-pack-name="relevancePackName"
      :enabled-plan-count="store.enabledPlanCount"
      :loading="store.loading"
    />

    <nav
      aria-label="采集策略类型"
      class="tabs"
    >
      <button
        v-for="tab in [{ value: 'keywords', label: '关键词包' }, { value: 'relevance', label: '全局相关性' }, { value: 'plans', label: '采集计划' }] as const"
        :key="tab.value"
        type="button"
        :class="{ active: store.activeTab === tab.value }"
        @click="store.activeTab = tab.value"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div
      v-if="store.error"
      class="error"
      role="alert"
    >
      !&nbsp; {{ store.error }}
    </div>

    <KeywordPackPanel
      v-if="store.activeTab === 'keywords'"
      :packs="store.packs"
      :selected="store.selectedPack"
      :loading="store.loading"
      :saving="store.saving"
      :toggle-reason="store.packToggleReason"
      @open="store.openPack"
      @toggle="store.togglePack"
      @add-keyword="addKeyword"
    />

    <RelevancePanel
      v-else-if="store.activeTab === 'relevance'"
      :packs="store.enabledPacks"
      :relevance="store.relevance"
      :saving="store.saving"
      @save="saveRelevance"
    />

    <template v-else>
      <section class="filters">
        <input
          v-model="store.filters.search"
          placeholder="搜索计划名称、Plan ID"
        ><select v-model="store.filters.enabled">
          <option value="">
            全部状态
          </option><option value="true">
            已启用
          </option><option value="false">
            已停用
          </option>
        </select><select v-model="store.filters.platform">
          <option value="">
            全部平台
          </option><option value="xhs">
            小红书
          </option><option value="douyin">
            抖音
          </option><option value="weibo">
            微博
          </option><option value="bilibili">
            B站
          </option><option value="kuaishou">
            快手
          </option>
        </select><span /><button
          type="button"
          @click="store.resetPlanFilters(); store.firstPlanPage()"
        >
          重置
        </button><button
          type="button"
          class="primary"
          @click="store.firstPlanPage()"
        >
          查询
        </button>
      </section>
      <PlanPanel
        :plans="store.plans"
        :packs="store.packs"
        :providers="providers"
        :total="store.planTotal"
        :offset="store.planOffset"
        :limit="store.planLimit"
        :loading="store.loading"
        :saving="store.saving"
        :toggle-reason="store.planToggleReason"
        @open="openPlan"
        @toggle="store.togglePlan"
        @previous="store.previousPlanPage"
        @next="store.nextPlanPage"
      />
    </template>

    <KeywordPackCreateDialog
      v-model="packDialogOpen"
      :saving="store.saving"
      @submit="savePack"
    />
    <PlanCreateDrawer
      v-model="planDrawerOpen"
      :packs="store.enabledPacks"
      :pack-details="store.packDetails"
      :capabilities="store.capabilities"
      :relevance-name="relevancePackName"
      :relevance-available="store.relevance !== null"
      :saving="store.saving"
      :loading-pack-details="store.loadingPackDetails"
      @load-pack-details="store.loadPackDetails"
      @submit="savePlan"
    />
    <PlanDetailDrawer
      v-model="planDetailOpen"
      :plan="store.selectedPlan"
      :packs="store.packs"
      :providers="providers"
    />
    <div
      v-if="notice"
      class="notice"
      role="status"
    >
      ✓ {{ notice }}
    </div>
  </AppShell>
</template>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }.page-header h1 { margin: 0; color: #172033; font-size: 26px; }.page-header p { margin: 7px 0 0; color: #6d778a; font-size: 13px; }.actions { display: flex; gap: 10px; }.actions button,.filters button { height: 40px; padding: 0 16px; border: 1px solid #d8dde6; border-radius: 7px; color: #3e485a; background: #fff; cursor: pointer; }.actions .outline { border-color: var(--aima-primary); color: var(--aima-primary); }.primary { border-color: var(--aima-primary) !important; color: #fff !important; background: var(--aima-primary) !important; }
.tabs { display: flex; gap: 26px; margin: 0 0 18px; border-bottom: 1px solid var(--aima-border); }.tabs button { height: 45px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: #536075; background: transparent; cursor: pointer; }.tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.filters { display: grid; grid-template-columns: minmax(260px, 1fr) 140px 140px 1fr auto auto; gap: 10px; margin-bottom: 16px; padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }.filters input,.filters select { height: 39px; padding: 0 11px; border: 1px solid #d9dfe8; border-radius: 6px; background: #fff; }
.error { margin-bottom: 15px; padding: 12px 14px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 13px; }.notice { position: fixed; z-index: 200; top: 76px; left: 50%; padding: 11px 18px; border: 1px solid #a9e3c7; border-radius: 7px; color: #12804b; background: #effbf5; box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
</style>
