<script setup lang="ts">
import type { CollectionPlanResponse, CollectionProviderConfigResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'

defineProps<{
  plans: CollectionPlanResponse[]
  packs: KeywordPackSummaryResponse[]
  providers: CollectionProviderConfigResponse[]
  total: number
  offset: number
  limit: number
  loading: boolean
  saving: boolean
}>()
const emit = defineEmits<{
  open: [plan: CollectionPlanResponse]
  toggle: [plan: CollectionPlanResponse]
  previous: []
  next: []
}>()

function packNames(plan: CollectionPlanResponse, packs: KeywordPackSummaryResponse[]): string {
  return plan.keyword_pack_ids.map((id) => packs.find((pack) => pack.id === id)?.name ?? id.slice(0, 8)).join('、')
}

function providerName(id: string, providers: CollectionProviderConfigResponse[]): string {
  return providers.find((provider) => provider.id === id)?.display_name ?? id.slice(0, 8)
}

function nextRun(value?: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '等待 Scheduler 初始化'
}
</script>

<template>
  <section class="plan-card">
    <div class="info">
      ⓘ&nbsp; 所有 Plan 运行时自动冻结当前全局 Relevance 配置，不能按 Plan 覆盖；重新启用从下一个 Cron 时刻开始，不补跑停用期间任务。
    </div>
    <div class="table-heading">
      <strong>找到 {{ total }} 条采集计划</strong><span>更新时间：最新优先</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>计划 / Plan ID</th><th>状态</th><th>Discovery 词包</th><th>目标平台 / Provider</th><th>调度与下次运行</th><th>采集策略</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-if="loading">
            <td
              colspan="7"
              class="state"
            >
              正在读取采集计划…
            </td>
          </tr>
          <tr v-else-if="plans.length === 0">
            <td
              colspan="7"
              class="state"
            >
              暂无周期采集计划。
            </td>
          </tr>
          <tr
            v-for="plan in plans"
            v-else
            :key="plan.id"
          >
            <td><strong>{{ plan.name }}</strong><small>Plan ID: {{ plan.id }}</small></td>
            <td><span :class="['status', plan.enabled ? 'enabled' : 'disabled']">● {{ plan.enabled ? '已启用' : '已停用' }}</span></td>
            <td>{{ packNames(plan, packs) }}<small>v{{ plan.schedule_version }}</small></td>
            <td>
              <span
                v-for="item in plan.platforms"
                :key="item.platform"
              >{{ item.platform }} · {{ providerName(item.provider_config_id, providers) }}<small /></span>
            </td>
            <td><strong>{{ plan.schedule_expr }}</strong><small>{{ nextRun(plan.next_run_at) }}</small></td>
            <td>详情：变化时<small>评论：自适应</small></td>
            <td class="actions">
              <button
                type="button"
                class="detail"
                @click="emit('open', plan)"
              >
                查看详情
              </button><button
                type="button"
                :disabled="saving"
                @click="emit('toggle', plan)"
              >
                {{ plan.enabled ? '停用' : '启用' }}
              </button>
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
.info { margin-bottom: 18px; padding: 12px 14px; border: 1px solid #b9d8ff; border-radius: 7px; color: #1768cc; background: #f0f7ff; font-size: 13px; }
.table-heading { display: flex; align-items: center; justify-content: space-between; margin: 16px 0 10px; }.table-heading span { padding: 8px 10px; border: 1px solid var(--aima-border); border-radius: 6px; color: #697589; background: #fff; font-size: 12px; }
.table-wrap { overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; }table { width: 100%; border-collapse: collapse; font-size: 13px; }th { height: 45px; color: #596579; background: #fafbfc; font-weight: 500; text-align: left; }th,td { padding: 12px 13px; border-bottom: 1px solid #edf0f4; vertical-align: middle; }td strong,td small { display: block; }td small { max-width: 210px; margin-top: 5px; overflow: hidden; color: #7f899b; text-overflow: ellipsis; white-space: nowrap; }
.status { display: inline-block; padding: 5px 8px; border-radius: 5px; font-size: 12px; }.enabled { color: #118852; background: #eaf8f1; }.disabled { color: #657084; background: #edf0f4; }
.actions { min-width: 120px; }.actions button { display: block; width: 78px; margin: 4px 0; padding: 5px 7px; border: 1px solid #d8dee8; border-radius: 5px; color: #5b6576; background: #fff; cursor: pointer; }.actions .detail { border-color: #f7a5c1; color: var(--aima-primary); }.actions button:disabled { opacity: .5; }
.state { height: 180px; color: #8993a4; text-align: center; }
.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 14px; color: #6f7a8d; font-size: 13px; }.pagination button { height: 34px; padding: 0 14px; border: 1px solid #d8dee8; border-radius: 6px; color: #526075; background: #fff; cursor: pointer; }.pagination button:disabled { opacity: .45; cursor: default; }
</style>
