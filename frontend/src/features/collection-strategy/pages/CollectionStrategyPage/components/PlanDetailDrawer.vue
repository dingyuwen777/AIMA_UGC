<script setup lang="ts">
import { ref, watch } from 'vue'

import type {
  BrandResponse,
  CollectionPlanResponse,
  CollectionProviderConfigResponse,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'
import { collectionSearchConfigSummary } from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDrawer from '../../../../../shared/ui/AimaDrawer.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { collectionPlatformLabel, collectionScheduleLabel, formatBeijingDateTime } from '../../../presentation'
import PlanResourceDetailDialog from './PlanResourceDetailDialog.vue'

const props = defineProps<{
  plan: CollectionPlanResponse | null
  packs: KeywordPackSummaryResponse[]
  brands: BrandResponse[]
  providers: CollectionProviderConfigResponse[]
  saving: boolean
  error?: string | null
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{
  edit: [plan: CollectionPlanResponse]
  copy: [plan: CollectionPlanResponse, name: string, onSaved: () => void]
  archive: [plan: CollectionPlanResponse]
}>()
const copied = ref(false)
const copyName = ref('')
const copyEditing = ref(false)
const selectedResource = ref<{ kind: 'pack'; id: string } | null>(null)

watch(() => props.plan?.id, () => { copyEditing.value = false })
watch(open, (value) => { if (!value) selectedResource.value = null })

/** 复制计划编号只存在于技术详情，提供短暂成功反馈。 */
async function copyPlanId(planId: string): Promise<void> {
  await navigator.clipboard.writeText(planId)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1600)
}

/** 业务视图不回退内部 ID；缺失目录项只标记为历史引用。 */
function packLabel(packId: string): string {
  const pack = props.packs.find((item) => item.id === packId)
  return pack ? `${pack.name} · v${pack.version}` : '历史词包（当前目录不可用）'
}

/** 把品牌引用转换成人类可读名称和角色，原始 ID 仅保留在技术详情。 */
function brandLabel(brandId: string): string {
  const brand = props.brands.find((item) => item.id === brandId)
  if (!brand) return '历史品牌（当前目录不可用）'
  const role = brand.role === 'owned' ? '自有品牌' : brand.role === 'competitor' ? '竞品品牌' : '其他品牌'
  return `${brand.display_name} · ${role}`
}

/** Provider 显示名只服务技术详情，不进入默认业务投影。 */
function providerLabel(providerId: string): string {
  return props.providers.find((provider) => provider.id === providerId)?.display_name ?? '历史采集配置'
}

/** 进入复制计划的行内编辑态。 */
function startCopy(): void {
  if (!props.plan) return
  copyName.value = `${props.plan.name} 副本`
  copyEditing.value = true
}

/** 提交计划副本名称，成功后退出行内编辑态。 */
function submitCopy(): void {
  if (!props.plan || !copyName.value.trim()) return
  emit('copy', props.plan, copyName.value.trim(), () => { copyEditing.value = false })
}

/** 二次确认后归档当前计划，既有运行不受影响。 */
function archivePlan(): void {
  if (!props.plan) return
  if (!window.confirm(`确认归档采集计划“${props.plan.name}”吗？归档只停止未来调度，已经创建的历史运行不会被取消或改写。`)) return
  emit('archive', props.plan)
}
</script>

<template>
  <AimaDrawer
    v-if="plan"
    v-model="open"
    label="采集计划详情"
    width="450px"
  >
    <template #header>
      <header>
        <div><h2>采集计划详情</h2><p>计划规则与执行范围</p></div><AimaButton
          variant="text"
          aria-label="关闭详情"
          @click="open = false"
        >
          <AimaIcon name="close" />
        </AimaButton>
      </header>
    </template>

    <div class="body">
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <span :class="['status', plan.enabled ? 'enabled' : 'disabled']">{{ plan.enabled ? '已启用' : '已停用' }}</span><h3>{{ plan.name }}</h3>
      <div
        class="resource-actions"
        aria-label="计划管理操作"
      >
        <AimaButton
          size="small"
          :disabled="saving"
          @click="emit('edit', plan)"
        >
          编辑计划
        </AimaButton>
        <AimaButton
          size="small"
          :disabled="saving"
          @click="startCopy"
        >
          复制
        </AimaButton>
        <AimaButton
          size="small"
          :disabled="saving"
          @click="archivePlan"
        >
          归档
        </AimaButton>
      </div>
      <div
        v-if="copyEditing"
        class="copy-editor"
      >
        <label><span>副本名称</span><input
          v-model="copyName"
          :disabled="saving"
          maxlength="200"
        ></label>
        <small>副本默认停用，不会自动进入调度。</small>
        <div>
          <AimaButton
            size="small"
            :disabled="saving"
            @click="copyEditing = false"
          >
            取消
          </AimaButton><AimaButton
            variant="primary"
            size="small"
            :disabled="saving || !copyName.trim()"
            @click="submitCopy"
          >
            创建副本
          </AimaButton>
        </div>
      </div>
      <dl class="summary-grid">
        <div><dt>执行周期</dt><dd>{{ collectionScheduleLabel(plan.schedule_expr) }}</dd></div>
        <div><dt>下次运行</dt><dd>{{ plan.next_run_at ? formatBeijingDateTime(plan.next_run_at) : '等待调度初始化' }}</dd></div>
      </dl>
      <section class="packs">
        <h4>搜索条件 · 关键词包（当前配置）</h4><button
          v-for="id in plan.keyword_pack_ids"
          :key="id"
          type="button"
          @click="selectedResource = { kind: 'pack', id }"
        >
          {{ packLabel(id) }}
        </button><em v-if="plan.keyword_pack_ids.length === 0">未选择关键词包</em>
      </section>
      <section class="brands">
        <h4>内容过滤条件 · 品牌（当前配置）</h4><span v-if="(plan.brand_ids ?? []).length === 0">全部启用品牌及车型</span><span
          v-for="id in plan.brand_ids ?? []"
          :key="id"
        >{{ brandLabel(id) }}</span>
      </section>
      <section class="channels">
        <h4>目标平台</h4><span
          v-for="item in plan.platforms"
          :key="item.platform"
        ><b>{{ collectionPlatformLabel(item.platform) }}</b><small>{{ collectionSearchConfigSummary(item.search_config) }}</small></span>
      </section>
      <AimaFeedbackBanner tone="info">
        每次执行冻结当时的 Keyword Pack 搜索词与品牌车型目录快照。
      </AimaFeedbackBanner>
      <section class="policy">
        <h4>自动采集规则</h4><div><span>内容详情<b>数据变化时更新</b></span><span>评论<b>自适应采集</b></span></div>
      </section>

      <details class="technical-details">
        <summary>技术详情</summary>
        <dl class="technical-grid">
          <div class="plan-id">
            <dt>
              <span>计划标识</span><AimaButton
                variant="text"
                size="small"
                icon="copy"
                :aria-label="copied ? '计划标识已复制' : '复制计划标识'"
                @click="copyPlanId(plan.id)"
              >
                {{ copied ? '已复制' : '复制' }}
              </AimaButton>
            </dt><dd>{{ plan.id }}</dd>
          </div>
          <div><dt>调度版本</dt><dd>{{ plan.schedule_version }}</dd></div>
          <div><dt>时区</dt><dd>{{ plan.timezone === 'Asia/Shanghai' ? '北京时间' : plan.timezone }}</dd></div>
          <div><dt>最近更新</dt><dd>{{ formatBeijingDateTime(plan.updated_at) }}</dd></div>
        </dl>
        <div class="technical-relations">
          <strong>引用标识</strong>
          <span
            v-for="id in plan.keyword_pack_ids"
            :key="`pack-${id}`"
          >词包：{{ id }}</span>
          <span
            v-for="id in plan.brand_ids ?? []"
            :key="`brand-${id}`"
          >品牌：{{ id }}</span>
          <span
            v-for="item in plan.platforms"
            :key="`provider-${item.platform}`"
          >{{ collectionPlatformLabel(item.platform) }} Provider：{{ providerLabel(item.provider_config_id) }} · {{ item.provider_config_id }}</span>
        </div>
      </details>
    </div>
  </AimaDrawer>
  <PlanResourceDetailDialog
    :resource="selectedResource"
    :packs="packs"
    @close="selectedResource = null"
  />
</template>

<style scoped>
header { display: flex; width: 100%; height: 84px; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--aima-border); background: #fff; }h2 { margin: 0; font-size: 19px; line-height: 24px; }header p { margin: 5px 0 0; color: #7a8496; font-size: 12px; line-height: 18px; }.body { width: 100%; min-height: 816px; padding: 20px 22px 28px; }.status { font-size: 12px; font-weight: 500; }.enabled { color: #118852; }.disabled { color: #687386; }h3 { margin: 14px 0 10px; color: var(--aima-text); font-size: 20px; }.resource-actions { display: flex; gap: 7px; margin-bottom: 14px; }.resource-actions :deep(.aima-button) { color: #657084; }
.copy-editor { display: grid; gap: 7px; margin: 10px 0 14px; padding: 10px; border: 1px solid var(--aima-border); border-radius: 7px; background: #fafbfc; }.copy-editor label { display: grid; gap: 5px; color: #6e798a; font-size: 11px; }.copy-editor input { height: 36px; padding: 0 9px; border: 1px solid #d9dee8; border-radius: 6px; }.copy-editor small { color: #818b9b; font-size: 11px; }.copy-editor > div { display: flex; justify-content: flex-end; gap: 7px; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 10px; }.summary-grid div { min-height: 62px; padding: 10px; border: 1px solid #e1e5ec; border-radius: 6px; background: #fafafc; }dt { color: #8490a2; font-size: 11px; }dd { margin: 6px 0 0; overflow-wrap: anywhere; color: #2e3645; font-size: 12px; }
section { margin-top: 24px; }section h4 { display: block; margin: 0 0 8px; color: #3d4557; font-size: 13px; font-weight: 500; }section > span { display: block; margin: 6px 0; padding: 8px 9px; border-radius: 6px; background: #f6f8fb; color: #4a566a; font-size: 12px; }.packs em { color: #8b95a5; font-size: 12px; font-style: normal; }.channels > span { display: flex; min-height: 64px; flex-direction: column; justify-content: center; padding: 12px 10px; background: #f7fafc; }section span b,section span small { display: block; }section span small { margin-top: 4px; color: #788397; }.body > :deep(.aima-feedback) { margin-top: 30px; }.policy { margin-top: 30px; }.policy > div { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.policy > div span { margin: 0; border: 1px solid #e1e5ec; background: #fff; }.policy b { display: block; margin-top: 4px; color: #263146; }
.technical-details { margin-top: 28px; padding: 10px 12px; border: 1px dashed var(--aima-border-strong); border-radius: 7px; color: #778294; font-size: 11px; }.technical-details summary { cursor: pointer; color: #566276; font-weight: 600; }.technical-grid { display: grid; grid-template-columns: 1fr; gap: 8px; margin-top: 10px; }.technical-grid div { min-height: 54px; padding: 10px; border: 1px solid #e1e5ec; border-radius: 6px; background: #fafafc; }.plan-id dt { display: flex; align-items: center; justify-content: space-between; }.plan-id :deep(.aima-button) { margin: -7px -5px -7px 0; }.technical-relations { display: grid; gap: 5px; margin-top: 10px; }.technical-relations strong { color: #657084; }.technical-relations span { overflow-wrap: anywhere; color: #8a93a3; }
.packs > button { display: inline-block; max-width: 100%; margin: 6px 6px 6px 0; padding: 8px 9px; border: 1px solid #dce4f0; border-radius: 6px; color: #384d6b; background: #f7faff; cursor: pointer; font: inherit; font-size: 12px; text-align: left; overflow-wrap: anywhere; }
</style>
