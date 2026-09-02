<script setup lang="ts">
import { ref } from 'vue'

import type {
  CollectionPlanResponse,
  CollectionProviderConfigResponse,
  KeywordPackSummaryResponse,
  VehicleModelResponse,
} from '../../../../../generated/api/client'
import { collectionSearchConfigSummary } from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { collectionPlatformLabel, collectionScheduleLabel, formatBeijingDateTime } from '../../../presentation'

const props = defineProps<{
  plan: CollectionPlanResponse | null
  packs: KeywordPackSummaryResponse[]
  vehicles: VehicleModelResponse[]
  providers: CollectionProviderConfigResponse[]
}>()
const open = defineModel<boolean>({ required: true })
const copied = ref(false)

/** 复制计划编号，并提供短暂的可见成功反馈。 */
async function copyPlanId(planId: string): Promise<void> {
  await navigator.clipboard.writeText(planId)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1600)
}

/** 使用完整 API 词包目录解析计划引用，目录缺失时保留原始 ID 便于排障。 */
function packLabel(packId: string): string {
  const pack = props.packs.find((item) => item.id === packId)
  return pack ? `${pack.name} · v${pack.version}` : packId
}

/** 使用跨状态车型目录解析历史计划；目录缺失时保留原始 ID，绝不猜测车型名称。 */
function vehicleLabel(vehicleId: string): string {
  const vehicle = props.vehicles.find((item) => item.id === vehicleId)
  return vehicle ? `${vehicle.display_name} · ${vehicle.code}` : vehicleId
}
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
        <div><h2>采集计划详情</h2><p>调度版本 v{{ plan.schedule_version }}</p></div><AimaButton
          variant="text"
          aria-label="关闭详情"
          @click="open = false"
        >
          <AimaIcon name="close" />
        </AimaButton>
      </header>
      <div class="body">
        <span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span><h3>{{ plan.name }}</h3><dl>
          <div class="plan-id">
            <dt>
              <span>计划编号</span><AimaButton
                variant="text"
                size="small"
                icon="copy"
                :aria-label="copied ? '计划编号已复制' : '复制计划编号'"
                @click="copyPlanId(plan.id)"
              >
                {{ copied ? '已复制' : '复制' }}
              </AimaButton>
            </dt><dd>{{ plan.id }}</dd>
          </div><div><dt>执行周期</dt><dd>{{ collectionScheduleLabel(plan.schedule_expr) }}</dd></div><div><dt>时区</dt><dd>{{ plan.timezone === 'Asia/Shanghai' ? '北京时间' : plan.timezone }}</dd></div><div><dt>下次运行</dt><dd>{{ plan.next_run_at ? formatBeijingDateTime(plan.next_run_at) : '等待调度系统初始化' }}</dd></div>
        </dl><section class="packs">
          <h4>关键词包</h4><span
            v-for="id in plan.keyword_pack_ids"
            :key="id"
          >{{ packLabel(id) }}</span><em v-if="plan.keyword_pack_ids.length === 0">未选择关键词包</em>
        </section><section class="vehicles">
          <h4>车型</h4><span
            v-for="id in plan.vehicle_model_ids ?? []"
            :key="id"
          >{{ vehicleLabel(id) }}</span><em v-if="(plan.vehicle_model_ids ?? []).length === 0">未选择车型</em>
        </section><section class="channels">
          <h4>目标平台 / 采集渠道</h4><span
            v-for="item in plan.platforms"
            :key="item.platform"
          ><b>{{ collectionPlatformLabel(item.platform) }} · {{ providers.find((provider) => provider.id === item.provider_config_id)?.display_name ?? item.provider_config_id }}</b><small>{{ collectionSearchConfigSummary(item.search_config) }}</small></span>
        </section><AimaFeedbackBanner tone="info">
          全局规则相关性不保存在计划中；每次运行创建时会冻结当时的系统全局配置。
        </AimaFeedbackBanner><section class="policy">
          <h4>系统固定规则</h4><div><span>内容详情<b>数据变化时更新</b></span><span>评论<b>自适应采集</b></span></div>
        </section>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 105; inset: 0; background: rgb(20 29 44 / 34%); }aside { position: absolute; top: 0; right: 0; display: flex; width: 450px; height: 100%; flex-direction: column; overflow: hidden; background: #fff; box-shadow: -10px 0 30px rgb(20 29 44 / 12%); }header { display: flex; min-height: 84px; flex: none; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--aima-border); background: #fff; }h2 { margin: 0; font-size: 19px; }header p { margin: 5px 0 0; color: #7a8496; font-size: 12px; }.body { min-height: 0; flex: 1; overflow-x: hidden; overflow-y: auto; padding: 20px 22px 28px; }.status { font-size: 12px; font-weight: 500; }.enabled { color: #118852; }.disabled { color: #687386; }h3 { margin: 14px 0; color: var(--aima-text); font-size: 20px; }dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }dl div { min-height: 62px; padding: 10px; border: 1px solid #e1e5ec; border-radius: 6px; background: #fafafc; }dt { color: #8490a2; font-size: 11px; }dd { margin: 6px 0 0; overflow-wrap: anywhere; color: #2e3645; font-size: 12px; }.plan-id dt { display: flex; align-items: center; justify-content: space-between; }.plan-id :deep(.aima-button) { margin: -7px -5px -7px 0; }
section { margin-top: 24px; }section h4 { display: block; margin: 0 0 8px; color: #3d4557; font-size: 13px; font-weight: 500; }section > span { display: block; margin: 6px 0; padding: 8px 9px; border-radius: 6px; background: #f6f8fb; color: #4a566a; font-size: 12px; }.packs > span,.vehicles > span { display: inline-block; width: max-content; max-width: 100%; margin-right: 6px; background: #f7faff; color: #384d6b; }.packs em,.vehicles em { color: #8b95a5; font-size: 12px; font-style: normal; }.channels > span { display: flex; min-height: 88px; flex-direction: column; justify-content: center; padding: 14px 12px; background: #f7fafc; }section span b, section span small { display: block; }section span small { margin-top: 4px; color: #788397; }.aima-feedback { margin-top: 30px; }.policy { margin-top: 30px; }.policy > div { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.policy > div span { margin: 0; border: 1px solid #e1e5ec; background: #fff; }.policy b { margin-top: 4px; color: #263146; }
</style>
