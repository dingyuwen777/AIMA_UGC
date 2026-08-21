<script setup lang="ts">
import type { CollectionPlanResponse, CollectionProviderConfigResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'

defineProps<{
  plan: CollectionPlanResponse | null
  packs: KeywordPackSummaryResponse[]
  providers: CollectionProviderConfigResponse[]
}>()
const open = defineModel<boolean>({ required: true })
</script>

<template>
  <div
    v-if="open && plan"
    class="backdrop"
    @click.self="open = false"
  >
    <aside
      role="dialog"
      aria-label="采集计划详情"
    >
      <header>
        <div><h2>采集计划详情</h2><p>Plan v{{ plan.schedule_version }}</p></div><button
          type="button"
          aria-label="关闭详情"
          @click="open = false"
        >
          ×
        </button>
      </header>
      <div class="body">
        <span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span><h3>{{ plan.name }}</h3><dl><div><dt>Plan ID</dt><dd>{{ plan.id }}</dd></div><div><dt>Cron</dt><dd>{{ plan.schedule_expr }}</dd></div><div><dt>时区</dt><dd>{{ plan.timezone }}</dd></div><div><dt>下次运行</dt><dd>{{ plan.next_run_at ? new Date(plan.next_run_at).toLocaleString('zh-CN') : '等待 Scheduler 初始化' }}</dd></div></dl><section>
          <strong>Discovery 词包</strong><span
            v-for="id in plan.keyword_pack_ids"
            :key="id"
          >{{ packs.find((pack) => pack.id === id)?.name ?? id }}</span>
        </section><section>
          <strong>目标平台 / Provider</strong><span
            v-for="item in plan.platforms"
            :key="item.platform"
          >{{ item.platform }} · {{ providers.find((provider) => provider.id === item.provider_config_id)?.display_name ?? item.provider_config_id }}</span>
        </section><div class="notice">
          全局 Relevance 不保存在 Plan 中；每次 Run 创建时冻结系统当前配置。
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 105; inset: 0; background: rgb(20 29 44 / 34%); }aside { position: absolute; top: 0; right: 0; width: 450px; height: 100%; background: #fff; box-shadow: -10px 0 30px rgb(20 29 44 / 12%); }header { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px; border-bottom: 1px solid var(--aima-border); }h2 { margin: 0; font-size: 19px; }header p { margin: 5px 0 0; color: #7a8496; }header button { border: 0; background: transparent; font-size: 27px; cursor: pointer; }.body { padding: 22px; }.status { padding: 5px 9px; border-radius: 5px; font-size: 12px; }.enabled { color: #118852; background: #eaf8f1; }.disabled { color: #687386; background: #eef1f5; }h3 { margin: 16px 0; font-size: 21px; }dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }dl div { padding: 11px; border: 1px solid #e1e5ec; border-radius: 6px; }dt { color: #8490a2; font-size: 11px; }dd { margin: 5px 0 0; overflow-wrap: anywhere; font-size: 13px; }section { margin-top: 20px; }section strong { display: block; margin-bottom: 9px; }section span { display: block; margin: 6px 0; padding: 9px 10px; border-radius: 6px; background: #f6f8fb; color: #4a566a; }.notice { margin-top: 22px; padding: 12px; border: 1px solid #b9d8ff; border-radius: 6px; color: #1768c7; background: #f1f7ff; font-size: 12px; }
</style>
