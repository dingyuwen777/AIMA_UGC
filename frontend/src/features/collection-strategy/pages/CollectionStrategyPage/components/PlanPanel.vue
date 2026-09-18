<script setup lang="ts">
import type {
  BrandResponse,
  CollectionPlanResponse,
  KeywordPackSummaryResponse,
  ResourceLifecycleResponse,
} from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { collectionPlatformLabel, collectionScheduleLabel, formatBeijingDateTime } from '../../../presentation'
import ArchivedResourcePanel from './ArchivedResourcePanel.vue'

withDefaults(defineProps<{
  plans: CollectionPlanResponse[]
  archived?: ResourceLifecycleResponse[]
  packs: KeywordPackSummaryResponse[]
  brands: BrandResponse[]
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
  deleteArchived: [item: ResourceLifecycleResponse]
  previous: []
  next: []
}>()

/**
 * 按列表密度组合真实词包与品牌过滤条件。
 * 目录缺失只说明这是历史引用，不把内部 UUID 暴露到普通视图。
 */
function discoveryScopeLines(
  plan: CollectionPlanResponse,
  packs: KeywordPackSummaryResponse[],
  brands: BrandResponse[],
): string[] {
  const packLines = plan.keyword_pack_ids.map((id) =>
    packs.find((pack) => pack.id === id)?.name ?? '历史词包（当前目录不可用）',
  )
  const brandLines = (plan.brand_ids ?? []).map((id) => {
    const brand = brands.find((item) => item.id === id)
    return `品牌：${brand?.display_name ?? '历史品牌（当前目录不可用）'}`
  })
  const filterLines = brandLines.length ? brandLines : ['品牌：全部启用品牌']
  const visible: string[] = []
  if (packLines[0]) visible.push(packLines[0])
  if (filterLines[0]) visible.push(filterLines[0])
  for (const line of [...packLines.slice(1), ...filterLines.slice(1)]) {
    if (visible.length >= 2) break
    visible.push(line)
  }
  const remaining = packLines.length + filterLines.length - visible.length
  return remaining > 0 ? [...visible, `另有 ${remaining} 项条件`] : visible
}

/** 用当前 Contract 中可直接计数的词包和平台给出无歧义摘要，不发明“采集范围”口径。 */
function planScopeSummary(plan: CollectionPlanResponse): string {
  return `${plan.keyword_pack_ids.length} 个关键词包 · ${plan.platforms.length} 个平台`
}

/** 普通列表只展示业务平台名称，内部采集配置身份不进入用户视图。 */
function channelLines(plan: CollectionPlanResponse): string[] {
  const lines = plan.platforms.map((item) => collectionPlatformLabel(item.platform))
  if (lines.length <= 2) return lines
  return [...lines.slice(0, 2), `另有 ${lines.length - 2} 个平台`]
}

/** 用北京时间分钟粒度展示下一运行时间，未初始化时显示业务状态。 */
function nextRun(value?: string | null): string {
  return value ? formatBeijingDateTime(value) : '等待调度初始化'
}
</script>

<template>
  <section class="plan-card">
    <AimaFeedbackBanner tone="info">
      每次执行时，系统自动保存关键词包、品牌车型范围和平台搜索配置；后续修改不影响历史运行。重新启用后从下一周期执行，不补跑停用期间任务。
    </AimaFeedbackBanner>
    <div class="table-heading">
      <strong>找到 {{ total }} 条采集计划</strong>
    </div>
    <div class="table-wrap">
      <div
        v-if="loading"
        class="table-state"
        role="status"
      >
        正在读取采集计划…
      </div>
      <div
        v-else-if="plans.length === 0"
        class="table-state"
      >
        <strong>暂无采集计划</strong><span>可新建采集计划，或调整当前筛选条件。</span>
      </div>
      <table
        v-else
        class="plan-table"
      >
        <thead><tr><th>采集计划</th><th>状态</th><th>搜索条件 / 品牌过滤</th><th>目标平台</th><th>调度与下次运行</th><th>操作</th></tr></thead>
        <tbody>
          <tr
            v-for="plan in plans"
            :key="plan.id"
          >
            <td><strong>{{ plan.name }}</strong><small>{{ planScopeSummary(plan) }}</small></td>
            <td><span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span></td>
            <td class="scope-lines">
              <span
                v-for="(line, index) in discoveryScopeLines(plan, packs, brands)"
                :key="`${plan.id}-scope-${index}`"
                :title="line"
              >{{ line }}</span>
            </td>
            <td class="channel-lines">
              <span
                v-for="(line, index) in channelLines(plan)"
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

    <ArchivedResourcePanel
      class="archived-plans"
      title="已归档采集计划"
      loading-message="正在加载已归档采集计划…"
      empty-message="暂无已归档采集计划 · 归档后的计划会显示在这里"
      :items="archived"
      :loading="loadingArchived"
      :saving="saving"
      @load="emit('loadArchived')"
      @restore="emit('restoreArchived', $event.id)"
      @request-delete="emit('deleteArchived', $event)"
    />
  </section>
</template>

<style scoped>
.plan-card > :deep(.aima-feedback) { min-height: 44px; align-items: center; padding: 10px 13px; }
.table-heading { display: flex; align-items: center; justify-content: space-between; margin: 25px 0 15px; }.table-heading strong { font-size: 14px; line-height: 22px; }
.table-wrap { min-height: 227px; overflow-x: auto; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }
.plan-table { width: 100%; min-width: 1210px; table-layout: fixed; border-collapse: collapse; font-size: 13px; }.plan-table th { height: 45px; color: #596579; background: #fafbfc; font-weight: 500; text-align: left; }.plan-table th,.plan-table td { padding: 10px 12px; border-bottom: 1px solid #edf0f4; vertical-align: middle; }.plan-table tbody tr { height: 82px; }.plan-table th:first-child { width: 18%; }.plan-table th:nth-child(2) { width: 8%; }.plan-table th:nth-child(3) { width: 18%; }.plan-table th:nth-child(4) { width: 23%; }.plan-table th:nth-child(5) { width: 21%; }.plan-table th:last-child { width: 12%; }.plan-table td strong,.plan-table td small { display: block; }.plan-table td small { max-width: 210px; margin-top: 4px; overflow: hidden; color: #7f899b; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; }.status::before { width: 7px; height: 7px; border-radius: 50%; background: currentColor; content: ''; }.enabled { color: #118852; }.disabled { color: #657084; }
.scope-lines span,.channel-lines span { display: block; overflow: hidden; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }.scope-lines span:nth-child(3),.channel-lines span:nth-child(3) { color: #7f899b; font-size: 12px; }
.actions :deep(.aima-button) { display: flex; width: 78px; height: 32px; margin: 3px 0; }
.table-state { display: grid; min-width: 100%; min-height: 225px; align-content: center; justify-items: center; gap: 6px; color: #8993a4; font-size: 12px; }.table-state strong { color: #313c4f; font-size: 14px; }.table-state span { color: #8993a4; font-size: 11px; }
.plan-table td strong { overflow-wrap: anywhere; }
.pagination { display: flex; align-items: center; justify-content: flex-start; gap: 12px; margin-top: 14px; color: #6f7a8d; font-size: 12px; }.pagination button { height: 32px; padding: 0 12px; border: 1px solid #d8dee8; border-radius: 6px; color: #526075; background: #fff; cursor: pointer; }.pagination button:disabled { opacity: .45; cursor: default; }
.archived-plans { margin-top: 31px; }
</style>
