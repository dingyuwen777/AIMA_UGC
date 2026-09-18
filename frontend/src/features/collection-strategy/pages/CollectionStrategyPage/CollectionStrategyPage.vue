<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type {
  CollectionPlanCreateRequest,
  CollectionPlanResponse,
  CollectionPlanUpdateRequest,
  KeywordPackKeywordCreateRequest,
  KeywordPackResponse,
  ResourceLifecycleResponse,
} from '../../../../generated/api/client'
import AppShell from '../../../../app/layouts/AppShell.vue'
import AimaButton from '../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaPageHeader from '../../../../shared/ui/AimaPageHeader.vue'
import { useCollectionStrategyStore } from '../../store'
import KeywordPackCreateDialog from './components/KeywordPackCreateDialog.vue'
import KeywordPackPanel from './components/KeywordPackPanel.vue'
import PlanCreateDrawer from './components/PlanCreateDrawer.vue'
import PlanDetailDrawer from './components/PlanDetailDrawer.vue'
import PlanFilterBar from './components/PlanFilterBar.vue'
import PlanPanel from './components/PlanPanel.vue'
import ResourceConfirmDialog from './components/ResourceConfirmDialog.vue'
import StrategyKpiCards from './components/StrategyKpiCards.vue'

type ResourceKind = 'keyword_pack' | 'plan'
type ResourceAction = 'archive' | 'delete'

interface ResourceConfirmTarget {
  kind: ResourceKind
  action: ResourceAction
  id: string
  name: string
}

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
const confirmTarget = ref<ResourceConfirmTarget | null>(null)

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

/** 一键复制当前词包，副本保持停用且不切换当前选择。 */
async function copyPack(): Promise<void> {
  if (await store.copySelectedPack()) showNotice('已复制词包，副本默认停用。')
}

/** 打开当前词包的归档确认。 */
function requestPackArchive(): void {
  const pack = store.selectedPack
  if (!pack) return
  store.error = null
  confirmTarget.value = { kind: 'keyword_pack', action: 'archive', id: pack.id, name: pack.name }
}

/** 请求永久删除一个已归档词包。 */
function requestPackDelete(item: ResourceLifecycleResponse): void {
  store.error = null
  confirmTarget.value = { kind: 'keyword_pack', action: 'delete', id: item.id, name: item.name }
}

/** 恢复归档词包，恢复后仍保持停用。 */
async function restoreArchivedPack(packId: string): Promise<void> {
  if (await store.restoreArchivedPack(packId)) showNotice('词包已恢复，当前保持停用。')
}

/** 打开新建计划抽屉并清空当前编辑上下文。 */
function openNewPlan(): void {
  store.error = null
  planEditorPlan.value = null
  store.selectedPlan = null
  planDrawerOpen.value = true
}

/** 保存周期采集计划成功后关闭抽屉并提示自动执行语义。 */
async function savePlan(request: CollectionPlanCreateRequest): Promise<void> {
  if (await store.savePlan(request)) {
    planDrawerOpen.value = false
    showNotice('采集计划已保存，将按设定周期自动执行。')
  }
}

/** 更新计划只影响后续采集，历史记录保持不变。 */
async function updatePlan(request: CollectionPlanUpdateRequest): Promise<void> {
  if (await store.updateExistingPlan(request)) {
    planDrawerOpen.value = false
    planEditorPlan.value = null
    showNotice('采集计划已更新；后续采集将使用新配置。')
  }
}

/** 选择当前计划并打开详情抽屉。 */
function openPlan(plan: CollectionPlanResponse): void {
  store.error = null
  store.selectedPlan = plan
}

/** 从详情进入同一计划的编辑抽屉。 */
function editPlan(plan: CollectionPlanResponse): void {
  store.selectedPlan = plan
  planEditorPlan.value = plan
  planDrawerOpen.value = true
}

/** 一键复制当前计划，副本保持停用且详情继续停留在原计划。 */
async function copyPlan(plan: CollectionPlanResponse): Promise<void> {
  store.selectedPlan = plan
  if (await store.copySelectedPlan()) showNotice('已复制采集计划，副本默认停用。')
}

/** 打开当前计划的归档确认。 */
function requestPlanArchive(plan: CollectionPlanResponse): void {
  store.error = null
  store.selectedPlan = plan
  confirmTarget.value = { kind: 'plan', action: 'archive', id: plan.id, name: plan.name }
}

/** 请求永久删除一个已归档计划。 */
function requestPlanDelete(item: ResourceLifecycleResponse): void {
  store.error = null
  confirmTarget.value = { kind: 'plan', action: 'delete', id: item.id, name: item.name }
}

/** 恢复归档计划，恢复后仍保持停用。 */
async function restoreArchivedPlan(planId: string): Promise<void> {
  if (await store.restoreArchivedPlan(planId)) showNotice('采集计划已恢复，当前保持停用。')
}

/** 执行已经由用户确认的资源生命周期动作。 */
async function confirmResourceAction(): Promise<void> {
  const target = confirmTarget.value
  if (!target) return

  let success = false
  let message = ''
  if (target.kind === 'keyword_pack' && target.action === 'archive') {
    success = await store.archiveSelectedPack()
    message = '词包已归档。'
  } else if (target.kind === 'keyword_pack' && target.action === 'delete') {
    success = await store.deleteArchivedPack(target.id)
    message = '归档词包已永久删除。'
  } else if (target.kind === 'plan' && target.action === 'archive') {
    success = await store.archiveSelectedPlan()
    message = '采集计划已归档；已经创建的运行不受影响。'
  } else {
    success = await store.deleteArchivedPlan(target.id)
    message = '归档采集计划已永久删除。'
  }

  if (!success) return
  confirmTarget.value = null
  showNotice(message)
}

/** 关闭资源确认弹窗并清理当前错误，避免旧错误带入下一次操作。 */
function closeConfirm(): void {
  confirmTarget.value = null
  store.error = null
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
      description="统一管理关键词包与周期采集计划，设置搜索范围、目标平台和执行周期。"
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
      v-if="store.error && !confirmTarget"
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
      @archive="requestPackArchive"
      @load-archived="store.loadArchivedPacks"
      @restore-archived="restoreArchivedPack"
      @delete-archived="requestPackDelete"
      @previous="store.previousPackPage"
      @next="store.nextPackPage"
    />

    <template v-else>
      <PlanFilterBar
        v-model:search="store.filters.search"
        v-model:enabled="store.filters.enabled"
        v-model:platform="store.filters.platform"
        @reset="store.resetPlanFilters(); store.firstPlanPage()"
        @query="store.firstPlanPage()"
      />
      <PlanPanel
        :plans="store.plans"
        :archived="store.archivedPlans"
        :packs="store.packCatalog"
        :brands="store.brandCatalog"
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
        @delete-archived="requestPlanDelete"
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
      :saving="store.saving"
      @edit="editPlan"
      @copy="copyPlan"
      @archive="requestPlanArchive"
    />
    <ResourceConfirmDialog
      :target="confirmTarget"
      :saving="store.saving"
      :error="store.error"
      @close="closeConfirm"
      @confirm="confirmResourceAction"
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
.tabs { display: flex; gap: 24px; min-height: 46px; margin: 0 0 20px; border-bottom: 1px solid var(--aima-border); }.tabs button { height: 46px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: #536075; background: transparent; cursor: pointer; font-size: 13px; }.tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 600; }
.page-error { margin-bottom: 14px; }.success-toast { position: fixed; z-index: 200; top: 8px; left: 50%; width: 360px; transform: translateX(-50%); box-shadow: 0 8px 24px rgb(22 29 43 / 12%); }
</style>
