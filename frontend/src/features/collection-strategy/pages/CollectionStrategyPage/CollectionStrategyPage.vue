<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { CollectionPlanCreateRequest, CollectionPlanResponse } from '../../../../generated/api/client'
import AppShell from '../../../../app/layouts/AppShell.vue'
import AimaButton from '../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../../shared/ui/AimaPageHeader.vue'
import { COLLECTION_PLATFORM_OPTIONS } from '../../presentation'
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
  () => store.packCatalog.find((pack) => pack.id === store.relevance?.keyword_pack_id)?.name ?? '',
)
const providers = computed(() => store.capabilities?.provider_configs ?? [])

onMounted(() => store.refresh())

/** 保存词包成功后关闭弹窗并给出用户反馈。 */
async function savePack(name: string, description: string, keywords: string[]): Promise<void> {
  if (await store.savePack(name, description, keywords)) {
    packDialogOpen.value = false
    showNotice('关键词包已保存。')
  }
}

/** 追加关键词并清空详情侧栏的输入值。 */
async function addKeyword(packId: string, text: string): Promise<void> {
  if (await store.addKeyword(packId, text)) showNotice('关键词已加入词包。')
}

/** 保存唯一全局相关性配置并显示成功反馈。 */
async function saveRelevance(packId: string): Promise<void> {
  if (await store.saveRelevance(packId)) showNotice('系统全局相关性已更新。')
}

/** 保存周期采集计划成功后关闭抽屉并提示调度语义。 */
async function savePlan(request: CollectionPlanCreateRequest): Promise<void> {
  if (await store.savePlan(request)) {
    planDrawerOpen.value = false
    showNotice('采集计划已保存，将由调度服务执行。')
  }
}

/** 选择当前计划并打开详情抽屉。 */
function openPlan(plan: CollectionPlanResponse): void {
  store.selectedPlan = plan
}

/** 显示会自动消失的页面级成功反馈。 */
function showNotice(message: string): void {
  notice.value = message
  window.setTimeout(() => { if (notice.value === message) notice.value = null }, 2600)
}
</script>

<template>
  <AppShell section-title="采集策略">
    <AimaPageHeader
      title="采集策略"
      description="统一管理关键词包、全局相关性与周期采集计划"
    >
      <template #actions>
        <AimaButton
          icon="refresh"
          @click="store.refresh()"
        >
          刷新数据
        </AimaButton><AimaButton
          variant="outline"
          icon="plus"
          @click="packDialogOpen = true"
        >
          新建词包
        </AimaButton><AimaButton
          variant="primary"
          icon="plus"
          @click="planDrawerOpen = true"
        >
          新建采集计划
        </AimaButton>
      </template>
    </AimaPageHeader>

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

    <AimaFeedbackBanner
      v-if="store.error"
      class="page-error"
      tone="error"
      role="alert"
    >
      {{ store.error }}
    </AimaFeedbackBanner>

    <KeywordPackPanel
      v-if="store.activeTab === 'keywords'"
      :packs="store.packs"
      :selected="store.selectedPack"
      :total="store.packTotal"
      :offset="store.packOffset"
      :limit="store.packLimit"
      :loading="store.loading"
      :saving="store.saving"
      :toggle-reason="store.packToggleReason"
      @open="store.openPack"
      @toggle="store.togglePack"
      @add-keyword="addKeyword"
      @previous="store.previousPackPage"
      @next="store.nextPackPage"
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
        <span class="search-field"><input
          v-model="store.filters.search"
          placeholder="搜索计划名称、Plan ID"
        ></span><select v-model="store.filters.enabled">
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
          </option><option
            v-for="option in COLLECTION_PLATFORM_OPTIONS"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select><span /><AimaButton
          @click="store.resetPlanFilters(); store.firstPlanPage()"
        >
          重置
        </AimaButton><AimaButton
          variant="primary"
          @click="store.firstPlanPage()"
        >
          查询
        </AimaButton>
      </section>
      <PlanPanel
        :plans="store.plans"
        :packs="store.packCatalog"
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
      :packs="store.packCatalog"
      :providers="providers"
    />
    <AimaFeedbackBanner
      v-if="notice"
      class="success-toast"
      tone="success"
      role="status"
    >
      {{ notice }}
    </AimaFeedbackBanner>
  </AppShell>
</template>

<style scoped>
.tabs { display: flex; gap: 28px; min-height: 46px; margin: 0 0 24px; border-bottom: 1px solid var(--aima-border); }.tabs button { height: 46px; padding: 0 2px; border: 0; border-bottom: 2px solid transparent; color: #536075; background: transparent; cursor: pointer; font-size: 13px; }.tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.filters { display: grid; grid-template-columns: 420px 120px 172px 1fr auto auto; gap: 8px; margin-bottom: 20px; padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }.filters input,.filters select { width: 100%; height: 40px; padding: 0 10px; border: 1px solid #d9dfe8; border-radius: 6px; color: var(--aima-text-secondary); background: #fff; font-size: 12px; }
.page-error { margin-bottom: 14px; }.success-toast { position: fixed; z-index: 200; top: 8px; left: 50%; width: 360px; transform: translateX(-50%); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
@media (max-width: 1260px) { .filters { grid-template-columns: minmax(240px, 1fr) 120px 150px auto auto; }.filters > span:nth-of-type(2) { display: none; } }
</style>
