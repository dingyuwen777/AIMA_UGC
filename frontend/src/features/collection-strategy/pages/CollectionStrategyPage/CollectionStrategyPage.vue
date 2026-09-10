<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type {
  CollectionPlanCreateRequest,
  CollectionPlanResponse,
  CollectionPlanUpdateRequest,
  KeywordPackKeywordCreateRequest,
  KeywordPackResponse,
} from '../../../../generated/api/client'
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
import StrategyKpiCards from './components/StrategyKpiCards.vue'

const store = useCollectionStrategyStore()
const packDialogOpen = ref(false)
const packEditorPack = ref<KeywordPackResponse | null>(null)
const planDrawerOpen = ref(false)
const planEditorPlan = ref<CollectionPlanResponse | null>(null)
const planDetailOpen = computed({
  get: () => store.selectedPlan !== null && !planDrawerOpen.value,
  set: (value: boolean) => { if (!value) store.selectedPlan = null },
})
const notice = ref<string | null>(null)
const providers = computed(() => store.capabilities?.provider_configs ?? [])

onMounted(() => store.refresh())

/** 保存词包成功后关闭弹窗并给出用户反馈。 */
async function savePack(name: string, description: string, keywords: KeywordPackKeywordCreateRequest[]): Promise<void> {
  const pack = packEditorPack.value
  const saved = pack
    ? await store.savePackChanges(pack.id, { expected_version: pack.version, name, description, keywords })
    : await store.savePack(name, description, keywords)
  if (saved) {
    packDialogOpen.value = false
    showNotice('关键词包已保存。')
  }
}

async function copyPack(name: string, onSaved: () => void): Promise<void> {
  if (await store.copySelectedPack(name)) {
    onSaved()
    showNotice('词包副本已创建，当前保持停用。')
  }
}

async function archivePack(): Promise<void> {
  if (await store.archiveSelectedPack()) showNotice('词包已归档。')
}

async function restoreArchivedPack(packId: string): Promise<void> {
  if (await store.restoreArchivedPack(packId)) showNotice('词包已恢复，当前保持停用。')
}

async function deleteArchivedPack(packId: string): Promise<void> {
  if (await store.deleteArchivedPack(packId)) showNotice('未被业务引用的归档词包已永久删除。')
}

function openNewPlan(): void {
  store.error = null
  planEditorPlan.value = null
  store.selectedPlan = null
  planDrawerOpen.value = true
}

/** 保存周期采集计划成功后关闭抽屉并提示调度语义。 */
async function savePlan(request: CollectionPlanCreateRequest): Promise<void> {
  if (await store.savePlan(request)) {
    planDrawerOpen.value = false
    showNotice('采集计划已保存，将由调度服务执行。')
  }
}

async function updatePlan(request: CollectionPlanUpdateRequest): Promise<void> {
  if (await store.updateExistingPlan(request)) {
    planDrawerOpen.value = false
    planEditorPlan.value = null
    showNotice('采集计划已更新；历史运行保持原配置。')
  }
}

/** 选择当前计划并打开详情抽屉。 */
function openPlan(plan: CollectionPlanResponse): void {
  store.error = null
  store.selectedPlan = plan
}

function editPlan(plan: CollectionPlanResponse): void {
  store.selectedPlan = plan
  planEditorPlan.value = plan
  planDrawerOpen.value = true
}

async function copyPlan(plan: CollectionPlanResponse, name: string, onSaved: () => void): Promise<void> {
  store.selectedPlan = plan
  if (await store.copySelectedPlan(name)) {
    onSaved()
    showNotice('采集计划副本已创建，当前保持停用。')
  }
}

async function archivePlan(plan: CollectionPlanResponse): Promise<void> {
  store.selectedPlan = plan
  if (await store.archiveSelectedPlan()) showNotice('采集计划已归档；已经创建的运行不受影响。')
}

async function restoreArchivedPlan(planId: string): Promise<void> {
  if (await store.restoreArchivedPlan(planId)) showNotice('采集计划已恢复，当前保持停用。')
}

async function deleteArchivedPlan(planId: string): Promise<void> {
  if (await store.deleteArchivedPlan(planId)) showNotice('从未执行且无历史引用的归档计划已永久删除。')
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
      description="统一管理 Provider 搜索词与独立的品牌过滤范围"
    >
      <template #actions>
        <AimaButton
          icon="refresh"
          :disabled="store.loading || store.saving"
          @click="store.refresh()"
        >
          刷新数据
        </AimaButton><AimaButton
          variant="primary"
          icon="plus"
          :disabled="store.loading || store.saving"
          @click="openNewPlan"
        >
          新建采集计划
        </AimaButton>
      </template>
    </AimaPageHeader>

    <StrategyKpiCards
      :pack-count="store.packTotal"
      :brand-count="store.enabledBrandCount"
      :enabled-plan-count="store.enabledPlanCount"
      :loading="store.loading"
    />

    <nav
      aria-label="采集策略类型"
      class="tabs"
    >
      <button
        v-for="tab in [{ value: 'keywords', label: '关键词包' }, { value: 'plans', label: '采集计划' }] as const"
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
      :archived="store.archivedPacks"
      :total="store.packTotal"
      :offset="store.packOffset"
      :limit="store.packLimit"
      :loading="store.loading"
      :loading-archived="store.loadingArchived"
      :saving="store.saving"
      :toggle-reason="store.packToggleReason"
      @create="store.error = null; packEditorPack = null; packDialogOpen = true"
      @edit="store.error = null; packEditorPack = store.selectedPack; packDialogOpen = true"
      @open="store.openPack"
      @toggle="store.togglePack"
      @copy="copyPack"
      @archive="archivePack"
      @load-archived="store.loadArchivedPacks"
      @restore-archived="restoreArchivedPack"
      @delete-archived="deleteArchivedPack"
      @previous="store.previousPackPage"
      @next="store.nextPackPage"
    />

    <template v-else>
      <section class="filters">
        <span class="search-field"><input
          v-model="store.filters.search"
          placeholder="搜索计划名称"
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
        :archived="store.archivedPlans"
        :packs="store.packCatalog"
        :brands="store.brandCatalog"
        :vehicles="store.vehicleCatalog"
        :providers="providers"
        :total="store.planTotal"
        :offset="store.planOffset"
        :limit="store.planLimit"
        :loading="store.loading"
        :loading-archived="store.loadingArchived"
        :saving="store.saving"
        :toggle-reason="store.planToggleReason"
        @open="openPlan"
        @toggle="store.togglePlan"
        @load-archived="store.loadArchivedPlans"
        @restore-archived="restoreArchivedPlan"
        @delete-archived="deleteArchivedPlan"
        @previous="store.previousPlanPage"
        @next="store.nextPlanPage"
      />
    </template>

    <KeywordPackCreateDialog
      v-model="packDialogOpen"
      :initial-pack="packEditorPack"
      :saving="store.saving"
      :error="store.error"
      @submit="savePack"
    />
    <PlanCreateDrawer
      v-model="planDrawerOpen"
      :error="store.error"
      :packs="planEditorPlan ? store.packCatalog : store.enabledPacks"
      :pack-details="store.packDetails"
      :capabilities="store.capabilities"
      :saving="store.saving"
      :loading-pack-details="store.loadingPackDetails"
      :initial-plan="planEditorPlan"
      @load-pack-details="store.loadPackDetails"
      @submit-create="savePlan"
      @submit-update="updatePlan"
    />
    <PlanDetailDrawer
      v-model="planDetailOpen"
      :error="store.error"
      :plan="store.selectedPlan"
      :packs="store.packCatalog"
      :brands="store.brandCatalog"
      :vehicles="store.vehicleCatalog"
      :providers="providers"
      :saving="store.saving"
      @edit="editPlan"
      @copy="copyPlan"
      @archive="archivePlan"
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
:deep(.aima-page-header) { margin-top: 4px; }
:deep(.aima-page-actions) { gap: 12px; }
@media (min-width: 1100px) { :deep(.aima-page-header) { flex-wrap: nowrap; align-items: center; }:deep(.aima-page-actions) { flex: none; justify-content: flex-end; } }
.tabs { display: flex; gap: 28px; min-height: 46px; margin: 0 0 20px; border-bottom: 1px solid var(--aima-border); }.tabs button { height: 46px; padding: 0 2px; border: 0; border-bottom: 2px solid transparent; color: #536075; background: transparent; cursor: pointer; font-size: 13px; }.tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.filters { display: grid; grid-template-columns: 420px 120px 172px 1fr auto auto; gap: 12px; height: 72px; margin-bottom: 20px; padding: 15px 16px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }.filters input,.filters select { width: 100%; height: 40px; padding: 0 10px; border: 1px solid #d9dfe8; border-radius: 6px; color: var(--aima-text-secondary); background: #fff; font-size: 12px; }
.page-error { margin-bottom: 14px; }.success-toast { position: fixed; z-index: 200; top: 8px; left: 50%; width: 360px; transform: translateX(-50%); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
@media (max-width: 1260px) { .filters { grid-template-columns: minmax(240px, 1fr) 120px 150px auto auto; }.filters > span:nth-of-type(2) { display: none; } }
</style>
