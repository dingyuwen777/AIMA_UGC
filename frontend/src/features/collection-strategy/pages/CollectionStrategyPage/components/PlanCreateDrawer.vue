<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type {
  CollectionCapabilitiesResponse,
  CollectionPlanCreateRequest,
  CollectionPlatform,
  CollectionSearchCapabilityResponse,
  CollectionSearchConfig,
  KeywordPackResponse,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'
import CollectionSearchConfigFields from '../../../../../shared/CollectionSearchConfigFields.vue'
import {
  fixedCollectionSearchConfig,
  isCollectionSearchConfigComplete,
} from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { planExecutionReason } from '../../../eligibility'
import { COLLECTION_PLATFORM_OPTIONS, COLLECTION_SCHEDULE_PRESETS } from '../../../presentation'

const props = defineProps<{
  packs: KeywordPackSummaryResponse[]
  packDetails: Record<string, KeywordPackResponse>
  capabilities: CollectionCapabilitiesResponse | null
  relevanceName: string
  relevanceAvailable: boolean
  saving: boolean
  loadingPackDetails: boolean
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{
  submit: [request: CollectionPlanCreateRequest]
  loadPackDetails: [packIds: string[]]
}>()

const platformOptions = COLLECTION_PLATFORM_OPTIONS
const name = ref('')
const scheduleExpr = ref('0 */6 * * *')
const enabled = ref(true)
const selectedPacks = ref<string[]>([])
const providerByPlatform = reactive<Partial<Record<CollectionPlatform, string>>>({})
const searchConfigByPlatform = reactive<Partial<Record<CollectionPlatform, CollectionSearchConfig>>>({})

const selectedPlatforms = computed(() =>
  platformOptions
    .filter((item) => providerByPlatform[item.value])
    .map((item) => ({
      platform: item.value,
      provider_config_id: providerByPlatform[item.value]!,
      search_config: searchConfigByPlatform[item.value] ?? {},
    })),
)

const eligibilityReason = computed(() => {
  const pendingProvider = platformOptions.find(
    (item) => isPlatformSelected(item.value) && !providerByPlatform[item.value],
  )
  if (pendingProvider) return `请选择${pendingProvider.label}的 Provider 配置。`

  const incompletePlatform = platformOptions.find((item) => {
    if (!providerByPlatform[item.value]) return false
    const capability = searchCapability(item.value)
    return !capability || !isCollectionSearchConfigComplete(capability, searchConfigByPlatform[item.value])
  })
  if (incompletePlatform) return `请完整选择${incompletePlatform.label}的采集参数。`

  return planExecutionReason({
    keywordPackIds: selectedPacks.value,
    platforms: selectedPlatforms.value,
    requireRelevance: enabled.value,
    relevanceAvailable: props.relevanceAvailable,
    packDetails: props.packDetails,
    capabilities: props.capabilities,
  })
})

watch(open, (value) => {
  if (!value) return
  name.value = ''
  scheduleExpr.value = '0 */6 * * *'
  enabled.value = true
  selectedPacks.value = []
  for (const option of platformOptions) {
    delete providerByPlatform[option.value]
    delete searchConfigByPlatform[option.value]
  }
})

watch(selectedPacks, (packIds) => {
  if (packIds.length) emit('loadPackDetails', [...packIds])
}, { deep: true })

/** 返回当前平台真实支持关键词搜索的 Provider 配置。 */
function configsFor(platform: CollectionPlatform) {
  const providers = new Set(
    (props.capabilities?.capabilities ?? [])
      .filter((item) => item.platform === platform && item.operations.includes('keyword_search'))
      .map((item) => item.provider),
  )
  return (props.capabilities?.provider_configs ?? []).filter((item) => providers.has(item.provider))
}

/** 解析已选 Provider 对应的动态 Search Capability。 */
function searchCapability(platform: CollectionPlatform): CollectionSearchCapabilityResponse | null {
  const providerConfig = props.capabilities?.provider_configs.find(
    (item) => item.id === providerByPlatform[platform],
  )
  if (!providerConfig) return null
  return props.capabilities?.capabilities.find(
    (item) => item.provider === providerConfig.provider && item.platform === platform,
  )?.search ?? null
}

/** Provider 变化时按后端 Capability 重建固定 Search Config 默认值。 */
function resetSearchConfig(platform: CollectionPlatform): void {
  const capability = searchCapability(platform)
  searchConfigByPlatform[platform] = capability ? fixedCollectionSearchConfig(capability) : {}
}

/** 用属性是否存在区分“尚未选择”和“已选择但等待选择 Provider”。 */
function isPlatformSelected(platform: CollectionPlatform): boolean {
  return Object.prototype.hasOwnProperty.call(providerByPlatform, platform)
}

/** 添加或移除平台；唯一 Provider 自动选中，多 Provider 保留人工选择。 */
function togglePlatform(platform: CollectionPlatform): void {
  if (isPlatformSelected(platform)) {
    delete providerByPlatform[platform]
    delete searchConfigByPlatform[platform]
    return
  }
  const configs = configsFor(platform)
  if (configs.length === 0) return
  providerByPlatform[platform] = configs.length === 1 ? configs[0]!.id : ''
  if (providerByPlatform[platform]) resetSearchConfig(platform)
}

/** 资格完整时组装现有 Contract 并提交，不引入计划级相关性覆盖。 */
function submit(): void {
  if (!name.value.trim() || eligibilityReason.value) return
  emit('submit', {
    name: name.value.trim(),
    schedule_expr: scheduleExpr.value,
    keyword_pack_ids: selectedPacks.value,
    platforms: selectedPlatforms.value,
    enabled: enabled.value,
  })
}
</script>

<template>
  <div
    v-if="open"
    class="backdrop"
    @click.self="open = false"
  >
    <aside
      role="dialog"
      aria-label="新建采集计划"
      aria-modal="true"
    >
      <header>
        <div><h2>新建采集计划</h2><p>保存关键词包与周期采集配置</p></div><AimaButton
          variant="text"
          aria-label="关闭"
          @click="open = false"
        >
          <AimaIcon name="close" />
        </AimaButton>
      </header>
      <div class="body">
        <label><strong>1. 计划名称</strong><input
          v-model="name"
          maxlength="200"
          placeholder="例如：爱玛新品口碑追踪"
        ></label>
        <fieldset>
          <legend>2. 关键词包</legend><label
            v-for="pack in packs"
            :key="pack.id"
            class="check"
          ><input
            v-model="selectedPacks"
            type="checkbox"
            :value="pack.id"
          >{{ pack.name }} · v{{ pack.version }}</label><p v-if="packs.length === 0">
            请先创建启用且非空的关键词包。
          </p>
        </fieldset>
        <fieldset>
          <legend>3. 采集平台与 Provider</legend><div class="platforms">
            <div
              v-for="option in platformOptions"
              :key="option.value"
              :class="['platform', { active: isPlatformSelected(option.value), unavailable: configsFor(option.value).length === 0 }]"
              role="button"
              :tabindex="configsFor(option.value).length === 0 ? -1 : 0"
              @click="togglePlatform(option.value)"
              @keydown.enter="togglePlatform(option.value)"
            >
              <span>{{ option.label }}</span><select
                v-if="isPlatformSelected(option.value)"
                v-model="providerByPlatform[option.value]"
                :aria-label="`${option.label} Provider`"
                @click.stop
                @change="resetSearchConfig(option.value)"
              >
                <option
                  value=""
                  disabled
                >
                  请选择 Provider
                </option>
                <option
                  v-for="config in configsFor(option.value)"
                  :key="config.id"
                  :value="config.id"
                >
                  {{ config.display_name }}
                </option>
              </select><small v-else>{{ configsFor(option.value).length ? '点击添加' : '暂无可用配置' }}</small>
              <div
                v-if="providerByPlatform[option.value] && searchCapability(option.value)"
                class="platform-search"
                @click.stop
                @keydown.stop
              >
                <CollectionSearchConfigFields
                  :model-value="searchConfigByPlatform[option.value] ?? {}"
                  :capability="searchCapability(option.value)!"
                  :platform-label="option.label"
                  @update:model-value="searchConfigByPlatform[option.value] = $event"
                />
              </div>
            </div>
          </div>
        </fieldset>
        <label><strong>4. 执行周期</strong><span class="schedule-field"><select
          v-model="scheduleExpr"
          aria-label="执行周期"
        ><option
          v-for="preset in COLLECTION_SCHEDULE_PRESETS"
          :key="preset.value"
          :value="preset.value"
        >{{ preset.label }}</option></select><em>北京时间</em></span><small>按北京时间周期执行；一次性采集请前往采集运行中心。</small></label>
        <label class="switch"><strong>5. 创建后启用计划</strong><input
          v-model="enabled"
          type="checkbox"
        ></label>
        <div class="policy">
          <strong>固定执行规则</strong><div><span>内容详情<b>变化时采集</b></span><span>评论数据<b>自适应采集</b></span></div>
        </div>
        <AimaFeedbackBanner :tone="enabled && !relevanceAvailable ? 'error' : 'success'">
          <strong>全局相关性（系统唯一，不可覆盖）</strong><span>{{ relevanceName || '尚未配置' }}</span><small>创建启用计划前必须可用，后端仍会再次验证。</small>
        </AimaFeedbackBanner>
        <div
          v-if="eligibilityReason && selectedPacks.length && platformOptions.some((item) => isPlatformSelected(item.value))"
          class="eligibility"
          role="status"
        >
          {{ loadingPackDetails ? '正在读取实时资格…' : eligibilityReason }}
        </div>
        <AimaFeedbackBanner tone="warning">
          计划执行会发起真实 Provider 请求并可能产生费用；当前不提供预算或金额上限。
        </AimaFeedbackBanner>
      </div>
      <footer>
        <AimaButton @click="open = false">
          取消
        </AimaButton><AimaButton
          variant="primary"
          :disabled="saving || loadingPackDetails || !name.trim() || !!eligibilityReason"
          :title="eligibilityReason || undefined"
          @click="submit"
        >
          {{ saving ? '保存中…' : '保存采集计划' }}
        </AimaButton>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 100; inset: 0; background: rgb(20 29 44 / 34%); }
aside { position: fixed; top: 0; right: 0; bottom: 0; display: flex; width: 510px; height: 100vh; max-height: 100vh; flex-direction: column; overflow: hidden; background: #fff; box-shadow: -10px 0 30px rgb(20 29 44 / 12%); }
header { display: flex; min-height: 84px; flex: none; align-items: center; justify-content: space-between; padding: 16px 24px; border-bottom: 1px solid var(--aima-border); }header h2 { margin: 0; font-size: 20px; }header p { margin: 5px 0 0; color: #737e91; font-size: 12px; }
.body { min-height: 0; flex: 1; overflow: auto; padding: 20px 24px; }label,fieldset,.policy { display: block; margin: 0 0 18px; }label strong,legend,.policy > strong { display: block; margin-bottom: 8px; color: #253044; font-size: 13px; }input:not([type='checkbox']),select { width: 100%; height: 38px; padding: 0 11px; border: 1px solid #d9dee8; border-radius: 6px; background: #fff; }fieldset { padding: 0; border: 0; }.check { display: inline-flex; align-items: center; gap: 6px; margin: 0 22px 8px 0; padding: 0; border: 0; font-size: 12px; }
.platforms { display: grid; gap: 8px; }.platform { min-height: 78px; padding: 10px; border: 1px solid #dfe4ec; border-radius: 7px; cursor: pointer; }.platform.active { border-color: var(--aima-primary); background: #fff5f8; }.platform.unavailable { cursor: not-allowed; opacity: .58; }.platform span,.platform small { display: block; }.platform span { color: #263146; font-size: 13px; font-weight: 600; }.platform small { margin-top: 8px; color: #818b9d; }.platform > select { height: 30px; margin-top: 7px; font-size: 11px; }.platform-search { margin-top: 10px; }
.schedule-field { display: flex; align-items: center; border: 1px solid #d9dee8; border-radius: 6px; }.schedule-field select { border: 0; }.schedule-field em { padding: 0 10px; color: #576276; font-size: 12px; font-style: normal; white-space: nowrap; }label > small,.aima-feedback small { display: block; margin-top: 4px; color: inherit; opacity: .74; }
.policy > div { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.policy span { padding: 10px; border: 1px solid #e0e4eb; border-radius: 7px; color: #6a7588; font-size: 12px; }.policy b { display: block; margin-top: 4px; color: #263146; }
.aima-feedback { margin-bottom: 14px; }.aima-feedback strong,.aima-feedback span { display: block; }.aima-feedback span { margin-top: 3px; font-weight: 600; }
.switch { display: flex; align-items: center; justify-content: space-between; }.switch strong { margin: 0; }.switch input { width: 20px; height: 20px; accent-color: var(--aima-primary); }.eligibility { margin: -4px 0 14px; padding: 10px 11px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 12px; }
footer { display: flex; flex: none; gap: 12px; padding: 14px 24px; border-top: 1px solid var(--aima-border); background: #fff; }footer :deep(.aima-button) { height: 40px; flex: 1; }
</style>
