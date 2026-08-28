<script setup lang="ts">
import type { CollectionPlanResponse, CollectionProviderConfigResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { collectionPlatformLabel, collectionScheduleLabel, formatBeijingDateTime } from '../../../presentation'

defineProps<{
  plans: CollectionPlanResponse[]
  packs: KeywordPackSummaryResponse[]
  providers: CollectionProviderConfigResponse[]
  total: number
  offset: number
  limit: number
  loading: boolean
  saving: boolean
  toggleReason: (plan: CollectionPlanResponse) => string | null
}>()
const emit = defineEmits<{
  open: [plan: CollectionPlanResponse]
  toggle: [plan: CollectionPlanResponse]
  previous: []
  next: []
}>()

/** 使用完整 API 目录解析计划的词包名称，缺失项保留原始 ID。 */
function packNames(plan: CollectionPlanResponse, packs: KeywordPackSummaryResponse[]): string {
  return plan.keyword_pack_ids.map((id) => packs.find((pack) => pack.id === id)?.name ?? id.slice(0, 8)).join('、')
}

/** 把 Provider 配置 ID 转为后端返回的展示名称。 */
function providerName(id: string, providers: CollectionProviderConfigResponse[]): string {
  return providers.find((provider) => provider.id === id)?.display_name ?? id.slice(0, 8)
}

/** 用北京时间展示下一运行时间，未初始化时保留正式调度状态。 */
function nextRun(value?: string | null): string {
  return value ? formatBeijingDateTime(value) : '等待 Scheduler 初始化'
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
      <table>
        <thead><tr><th>计划 / 编号</th><th>状态</th><th>关键词包</th><th>目标平台 / 采集渠道</th><th>调度与下次运行</th><th>操作</th></tr></thead>
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
            <td><strong>{{ plan.name }}</strong><small>Plan ID: {{ plan.id }}</small></td>
            <td><span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span></td>
            <td>{{ packNames(plan, packs) }}</td>
            <td>
              <span
                v-for="item in plan.platforms"
                :key="item.platform"
                class="channel"
              >{{ collectionPlatformLabel(item.platform) }}<small>{{ providerName(item.provider_config_id, providers) }}</small></span>
            </td>
            <td><strong>{{ collectionScheduleLabel(plan.schedule_expr) }}</strong><small>下次：{{ nextRun(plan.next_run_at) }}</small></td>
            <td class="actions">
              <AimaButton
                variant="text"
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
  </section>
</template>

<style scoped>
.table-heading { display: flex; align-items: center; justify-content: space-between; margin: 26px 0 14px; }.table-heading strong { font-size: 13px; }
.table-wrap { overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 12px; }th { height: 42px; color: #596579; background: #fafbfc; font-weight: 500; text-align: left; }th,td { padding: 11px 12px; border-bottom: 1px solid #edf0f4; vertical-align: middle; }th:first-child { width: 23%; }th:nth-child(2) { width: 9%; }th:nth-child(3) { width: 17%; }th:nth-child(4) { width: 19%; }th:nth-child(5) { width: 20%; }th:last-child { width: 12%; }td strong,td small { display: block; }td small { max-width: 210px; margin-top: 4px; overflow: hidden; color: #7f899b; text-overflow: ellipsis; white-space: nowrap; }
.status { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; }.status::before { width: 7px; height: 7px; border-radius: 50%; background: currentColor; content: ''; }.enabled { color: #118852; }.disabled { color: #657084; }
.channel { display: block; }.channel + .channel { margin-top: 6px; }
.actions :deep(.aima-button) { display: flex; width: 78px; margin: 4px 0; }
.state { height: 180px; color: #8993a4; text-align: center; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 14px; color: #6f7a8d; font-size: 13px; }.pagination button { height: 34px; padding: 0 14px; border: 1px solid #d8dee8; border-radius: 6px; color: #526075; background: #fff; cursor: pointer; }.pagination button:disabled { opacity: .45; cursor: default; }
</style>
