<script setup lang="ts">
import type {
  CollectionPlanResponse,
  CollectionProviderConfigResponse,
  KeywordPackSummaryResponse,
  ResourceLifecycleResponse,
  VehicleModelResponse,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { collectionPlatformLabel, collectionScheduleLabel, formatBeijingDateTime } from '../../../presentation'

withDefaults(defineProps<{
  plans: CollectionPlanResponse[]
  archived?: ResourceLifecycleResponse[]
  packs: KeywordPackSummaryResponse[]
  vehicles: VehicleModelResponse[]
  providers: CollectionProviderConfigResponse[]
  total: number
  offset: number
  limit: number
  loading: boolean
  loadingArchived?: boolean
  saving: boolean
  toggleReason: (plan: CollectionPlanResponse) => string | null
}>(), {
  archived: () => [],
  loadingArchived: false,
})
const emit = defineEmits<{
  open: [plan: CollectionPlanResponse]
  toggle: [plan: CollectionPlanResponse]
  loadArchived: []
  restoreArchived: [planId: string]
  deleteArchived: [planId: string]
  previous: []
  next: []
}>()

/**
 * 按列表密度组合真实词包与车型范围。
 * 目录缺失只说明这是历史引用，不把内部 UUID 暴露到普通视图。
 */
function discoveryScopeLines(
  plan: CollectionPlanResponse,
  packs: KeywordPackSummaryResponse[],
  vehicles: VehicleModelResponse[],
): string[] {
  const packLines = plan.keyword_pack_ids.map((id) =>
    packs.find((pack) => pack.id === id)?.name ?? '历史词包（当前目录不可用）',
  )
  const vehicleLines = (plan.vehicle_model_ids ?? []).map((id) => {
    const vehicle = vehicles.find((item) => item.id === id)
    return `车型：${vehicle?.display_name ?? '历史车型（当前目录不可用）'}`
  })
  const visible: string[] = []
  if (packLines[0]) visible.push(packLines[0])
  if (vehicleLines[0]) visible.push(vehicleLines[0])
  for (const line of [...packLines.slice(1), ...vehicleLines.slice(1)]) {
    if (visible.length >= 2) break
    visible.push(line)
  }
  const remaining = packLines.length + vehicleLines.length - visible.length
  return remaining > 0 ? [...visible, `另有 ${remaining} 项范围`] : visible
}

/** Provider 配置缺失时只显示历史配置提示；原始 ID 留在技术详情。 */
function providerName(id: string, providers: CollectionProviderConfigResponse[]): string {
  return providers.find((provider) => provider.id === id)?.display_name ?? '历史采集配置'
}

/** 按列表密度展示前两个真实平台/Provider，剩余平台做数量汇总。 */
function channelLines(
  plan: CollectionPlanResponse,
  providers: CollectionProviderConfigResponse[],
): string[] {
  const lines = plan.platforms.map(
    (item) => `${collectionPlatformLabel(item.platform)} · ${providerName(item.provider_config_id, providers)}`,
  )
  if (lines.length <= 2) return lines
  return [...lines.slice(0, 2), `另有 ${lines.length - 2} 个平台`]
}

/** 用北京时间分钟粒度展示下一运行时间，未初始化时显示业务状态。 */
function nextRun(value?: string | null): string {
  return value ? formatBeijingDateTime(value) : '等待调度初始化'
}

function onArchivedToggle(event: Event): void {
  if ((event.currentTarget as HTMLDetailsElement).open) emit('loadArchived')
}

function deleteArchived(item: ResourceLifecycleResponse): void {
  if (!window.confirm(`确认永久删除已归档采集计划“${item.name}”吗？只有从未执行且没有历史引用的计划才会被服务端允许删除。`)) return
  emit('deleteArchived', item.id)
}
</script>

<template>
  <section class="plan-card">
    <AimaFeedbackBanner tone="info">
      采集计划执行时会冻结当时的全局相关性配置；重新启用后从下一调度周期开始执行，不补跑停用期间任务。
    </AimaFeedbackBanner>
    <div class="table-heading">
      <strong>找到 {{ total }} 条采集计划</strong>
    </div>
    <div class="table-wrap">
      <table class="plan-table">
        <thead><tr><th>计划</th><th>状态</th><th>词包 / 车型</th><th>目标平台 / 采集渠道</th><th>调度与下次运行</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-if="loading">
            <td
              colspan="6"
              class="state"
            >
              正在读取采集计划…
            </td>
          </tr>
          <tr v-else-if="plans.length === 0">
            <td
              colspan="6"
              class="state"
            >
              暂无采集计划
            </td>
          </tr>
          <tr
            v-for="plan in plans"
            v-else
            :key="plan.id"
          >
            <td><strong>{{ plan.name }}</strong><small>更新于 {{ formatBeijingDateTime(plan.updated_at) }}</small></td>
            <td><span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span></td>
            <td class="scope-lines">
              <span
                v-for="(line, index) in discoveryScopeLines(plan, packs, vehicles)"
                :key="`${plan.id}-scope-${index}`"
                :title="line"
              >{{ line }}</span>
            </td>
            <td class="channel-lines">
              <span
                v-for="(line, index) in channelLines(plan, providers)"
                :key="`${plan.id}-channel-${index}`"
                :title="line"
              >{{ line }}</span>
            </td>
            <td><strong>{{ collectionScheduleLabel(plan.schedule_expr) }}</strong><small>{{ nextRun(plan.next_run_at) }}</small></td>
            <td class="actions">
              <AimaButton
                variant="secondary"
                size="small"
                @click="emit('open', plan)"
              >
                查看详情
              </AimaButton><AimaButton
                variant="secondary"
                size="small"
                :disabled="saving || !!toggleReason(plan)"
                :title="toggleReason(plan) || undefined"
                @click="emit('toggle', plan)"
              >
                {{ plan.enabled ? '停用' : '启用' }}
              </AimaButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <nav
      v-if="total > limit"
      class="pagination"
      aria-label="采集计划分页"
    >
      <button
        type="button"
        :disabled="loading || offset === 0"
        @click="emit('previous')"
      >
        上一页
      </button><span>第 {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }} 页</span><button
        type="button"
        :disabled="loading || offset + limit >= total"
        @click="emit('next')"
      >
        下一页
      </button>
    </nav>

    <details class="archived-plans" @toggle="onArchivedToggle">
      <summary>已归档采集计划</summary>
      <div v-if="loadingArchived" class="archived-state">正在读取…</div>
      <div v-else-if="archived.length === 0" class="archived-state">暂无已归档计划。</div>
      <div v-for="item in archived" v-else :key="item.id" class="archived-row">
        <span><strong>{{ item.name }}</strong><small>归档于 {{ formatBeijingDateTime(item.archived_at) }}</small></span>
        <AimaButton variant="text" size="small" :disabled="saving" @click="emit('restoreArchived', item.id)">恢复</AimaButton>
        <AimaButton variant="text" size="small" :disabled="saving" @click="deleteArchived(item)">永久删除</AimaButton>
      </div>
    </details>
  </section>
</template>

<style scoped>
.plan-card > :deep(.aima-feedback) { min-height: 44px; align-items: center; padding: 10px 13px; }
.table-heading { display: flex; align-items: center; justify-content: space-between; margin: 25px 0 15px; }.table-heading strong { font-size: 14px; line-height: 22px; }
.table-wrap { min-height: 227px; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 13px; }th { height: 45px; color: #596579; background: #fafbfc; font-weight: 500; text-align: left; }th,td { padding: 10px 12px; border-bottom: 1px solid #edf0f4; vertical-align: middle; }tbody tr { height: 82px; }th:first-child { width: 18%; }th:nth-child(2) { width: 8%; }th:nth-child(3) { width: 18%; }th:nth-child(4) { width: 23%; }th:nth-child(5) { width: 21%; }th:last-child { width: 12%; }td strong,td small { display: block; }td small { max-width: 210px; margin-top: 4px; overflow: hidden; color: #7f899b; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; }.status::before { width: 7px; height: 7px; border-radius: 50%; background: currentColor; content: ''; }.enabled { color: #118852; }.disabled { color: #657084; }
.scope-lines span,.channel-lines span { display: block; overflow: hidden; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }.scope-lines span:nth-child(3),.channel-lines span:nth-child(3) { color: #7f899b; font-size: 12px; }
.actions :deep(.aima-button) { display: flex; width: 78px; height: 32px; margin: 3px 0; }
.state { height: 180px; color: #8993a4; text-align: center; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 14px; color: #6f7a8d; font-size: 12px; }.pagination button { height: 32px; padding: 0 12px; border: 1px solid #d8dee8; border-radius: 6px; color: #526075; background: #fff; cursor: pointer; }.pagination button:disabled { opacity: .45; cursor: default; }
.archived-plans { margin-top: 14px; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }.archived-plans summary { padding: 12px 16px; cursor: pointer; color: #536075; font-size: 12px; font-weight: 600; }.archived-state { padding: 16px; color: #8993a4; font-size: 12px; }.archived-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 8px; padding: 10px 16px; border-top: 1px solid #edf0f4; }.archived-row strong,.archived-row small { display: block; }.archived-row strong { color: #313c4f; font-size: 12px; }.archived-row small { margin-top: 3px; color: #929baa; font-size: 10px; }
</style>