<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type {
  CollectionCapabilitiesResponse, CollectionPlatform, CollectionRunCreateRequest,
  CollectionRunCreatedResponse, CollectionSearchConfig, CollectionSearchCapabilityResponse,
  CollectionSupplementTargetSelection, KeywordPackSummaryResponse,
  CollectionAccountTargetRequest, ProviderAccountCapabilityV1,
} from '../../../../../generated/api/client'
import CollectionSearchConfigFields from '../../../../../shared/CollectionSearchConfigFields.vue'
import BrandMultiSelect from '../../../../../shared/BrandMultiSelect.vue'
import { isCollectionSearchConfigComplete } from '../../../../../shared/collectionSearchConfig'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'
import AimaDateRange from '../../../../../shared/ui/AimaDateRange.vue'
import { beijingDayBoundary } from '../../../../../shared/domain/beijingTime'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import CollectionSupplementOptions from '../../../../collection-supplement/CollectionSupplementOptions.vue'
import { useCollectionSupplement } from '../../../../collection-supplement/useCollectionSupplement'
import { manualCommentDefaults } from '../../../../collection-supplement/defaults'
import { platformLabels } from '../../../format'

const props = defineProps<{
  modelValue: boolean; capabilities: CollectionCapabilitiesResponse | null
  keywordPacks: KeywordPackSummaryResponse[]; creating: boolean; error: string | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]; submit: [request: CollectionRunCreateRequest]
  created: [result: CollectionRunCreatedResponse]
}>()
const mode = ref<'discovery' | 'content_supplement' | 'account_discovery'>('content_supplement')
const accounts = ref<CollectionAccountTargetRequest[]>([])
const accountConfirmation = ref(false)
const publishedRange = ref({ from: '', to: '' })
const publishedFrom = computed(() => publishedRange.value.from)
const publishedTo = computed(() => publishedRange.value.to)
const selectedPackIds = ref<string[]>([])
const brandScope = ref<'all_active' | 'selected'>('all_active')
const selectedBrandIds = ref<string[]>([])
const platforms = ref<CollectionPlatform[]>([])
const providerConfigId = ref('')
const includeComments = ref<boolean>(manualCommentDefaults.includeComments)
const includeSubComments = ref<boolean>(manualCommentDefaults.includeSubComments)
const searchConfigByPlatform = reactive<Partial<Record<CollectionPlatform, CollectionSearchConfig>>>({})
const active = computed(() => props.modelValue && mode.value === 'content_supplement')
const targets = computed<CollectionSupplementTargetSelection | null>(() => {
  const from = beijingDayBoundary(publishedFrom.value, 'start')
  const to = beijingDayBoundary(publishedTo.value, 'end')
  return from && to && from <= to ? { kind: 'published_date_range', published_from: from, published_to: to } : null
})
const supplement = useCollectionSupplement(active, targets, () => props.capabilities)
const busy = computed(() => props.creating || supplement.creating)
const provider = computed(() => props.capabilities?.provider_configs.find((item) => item.id === providerConfigId.value))
const availablePlatforms = computed(() => props.capabilities?.capabilities.filter((item) =>
  item.provider === provider.value?.provider && [mode.value === 'account_discovery' ? 'account_discovery' : 'keyword_search', 'content_detail',
    ...(includeComments.value ? ['comments'] : []), ...(includeSubComments.value ? ['sub_comments'] : []),
  ].every((operation) => item.operations.some((value) => value === operation)),
).map((item) => item.platform as CollectionPlatform) ?? [])
function searchCapability(platform: CollectionPlatform): CollectionSearchCapabilityResponse | null {
  return props.capabilities?.capabilities.find((item) => item.platform === platform && item.provider === provider.value?.provider)?.search ?? null
}
function accountCapability(platform: CollectionPlatform): ProviderAccountCapabilityV1 | null {
  return props.capabilities?.capabilities.find((item) => item.platform === platform && item.provider === provider.value?.provider)?.account ?? null
}
const accountIdLabels: Record<CollectionAccountTargetRequest['account_id_type'], string> = {
  red_id: '小红书号', user_id: '用户 ID', unique_id: '抖音号', sec_uid: '稳定用户 ID',
  uid: 'UID', kuaishou_id: '快手号', eid: '主页 EID',
}
function addAccount(platform: CollectionPlatform): void {
  const capability = accountCapability(platform)
  if (capability) accounts.value.push({ platform, account_id_type: capability.default_id_type, account_id: '', nickname: '' })
}
const normalizedAccounts = computed(() => accounts.value.filter((account) => platforms.value.includes(account.platform)).map((account) => ({
  ...account, account_id: account.account_id.trim(), nickname: account.nickname?.trim() || null,
})))
const accountRequest = computed<CollectionRunCreateRequest | null>(() => {
  if (!targets.value || targets.value.kind !== 'published_date_range' || !provider.value || platforms.value.length === 0) return null
  const rows = normalizedAccounts.value
  if (!platforms.value.every((platform) => rows.some((row) => row.platform === platform))
    || rows.length > 100 || rows.some((row) => !row.account_id || /\s/.test(row.account_id)
      || ((row.account_id_type === 'uid' || (row.platform === 'kuaishou' && row.account_id_type === 'user_id')) && !/^[0-9]+$/.test(row.account_id))
      || !accountCapability(row.platform)?.supported_id_types.includes(row.account_id_type))) return null
  const identities = rows.map((row) => `${row.platform}:${row.account_id_type}:${row.account_id}`)
  if (new Set(identities).size !== identities.length) return null
  return {
    mode: 'account_discovery',
    account_selection: { kind: 'accounts', accounts: rows, published_from: targets.value.published_from!, published_to: targets.value.published_to! },
    platforms: platforms.value.map((platform) => ({ platform, provider_config_id: providerConfigId.value })),
    include_comments: includeComments.value, include_sub_comments: includeSubComments.value,
  }
})
const canSubmit = computed(() => mode.value === 'content_supplement' ? supplement.canSubmit :
  mode.value === 'account_discovery' ? !busy.value && accountRequest.value !== null :
  !busy.value && Boolean(provider.value) && platforms.value.length > 0 && selectedPackIds.value.length > 0
  && (brandScope.value === 'all_active' || selectedBrandIds.value.length > 0)
  && platforms.value.every((platform) => {
    const capability = searchCapability(platform)
    return capability && isCollectionSearchConfigComplete(capability, searchConfigByPlatform[platform])
  }),
)
watch(() => props.modelValue, (open) => {
  if (!open) return
  mode.value = 'content_supplement'
  publishedRange.value = { from: '', to: '' }
  selectedPackIds.value = []; selectedBrandIds.value = []; brandScope.value = 'all_active'
  platforms.value = []
  accounts.value = []; accountConfirmation.value = false
  includeComments.value = manualCommentDefaults.includeComments
  includeSubComments.value = manualCommentDefaults.includeSubComments
  providerConfigId.value = props.capabilities?.provider_configs.length === 1 ? props.capabilities.provider_configs[0]?.id ?? '' : ''
})
watch(providerConfigId, () => { platforms.value = [] })
watch(mode, (current) => {
  accountConfirmation.value = false
  if (current === 'account_discovery') for (const platform of platforms.value) {
    if (!accounts.value.some((account) => account.platform === platform)) addAccount(platform)
  }
})
watch(platforms, (selected) => {
  accounts.value = accounts.value.filter((account) => selected.includes(account.platform))
  if (mode.value === 'account_discovery') for (const platform of selected) {
    if (!accounts.value.some((account) => account.platform === platform)) addAccount(platform)
  }
})
watch(() => JSON.stringify(accountRequest.value), () => { accountConfirmation.value = false })
watch(availablePlatforms, () => { platforms.value = platforms.value.filter((platform) => availablePlatforms.value.includes(platform)) })
watch(includeComments, (enabled) => { if (!enabled) includeSubComments.value = false })
function togglePlatform(platform: CollectionPlatform): void {
  platforms.value = platforms.value.includes(platform) ? platforms.value.filter((item) => item !== platform) : [...platforms.value, platform]
  const capability = searchCapability(platform)
  if (capability && platforms.value.includes(platform)) searchConfigByPlatform[platform] = { ...capability.manual_default }
}
/** 日期入口交给共享预览和创建逻辑；关键词发现保留原有配置。 */
async function submit(): Promise<void> {
  if (!canSubmit.value) return
  if (mode.value === 'content_supplement') {
    const created = await supplement.create()
    if (created) emit('created', created)
    return
  }
  if (mode.value === 'account_discovery') {
    if (!accountConfirmation.value) { accountConfirmation.value = true; return }
    if (accountRequest.value) emit('submit', accountRequest.value)
    return
  }
  emit('submit', {
    mode: 'discovery', keyword_pack_ids: selectedPackIds.value,
    brand_ids: brandScope.value === 'selected' ? selectedBrandIds.value : [],
    platforms: platforms.value.map((platform) => ({ platform, provider_config_id: providerConfigId.value, search_config: searchConfigByPlatform[platform] })),
    include_comments: includeComments.value, include_sub_comments: includeSubComments.value,
  })
}
</script>
<template>
  <AimaModalContainer
    :model-value="modelValue"
    label="新建辅助补采"
    width="840px"
    height="800px"
    :close-disabled="busy"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header class="dialog-header">
        <div><strong>新建辅助补采</strong><span>创建辅助补采任务</span></div><AimaButton
          variant="text"
          size="small"
          aria-label="关闭"
          :disabled="busy"
          @click="emit('update:modelValue', false)"
        >
          关闭
        </AimaButton>
      </header>
    </template>
    <div class="dialog-body">
      <nav class="mode-tabs">
        <button
          type="button"
          :class="{ active: mode === 'discovery' }"
          :disabled="busy"
          @click="mode = 'discovery'"
        >
          独立发现新内容
        </button>
        <button
          type="button"
          :class="{ active: mode === 'content_supplement' }"
          :disabled="busy"
          @click="mode = 'content_supplement'"
        >
          按发布时间补采
        </button>
        <button
          type="button"
          :class="{ active: mode === 'account_discovery' }"
          :disabled="busy"
          @click="mode = 'account_discovery'"
        >
          按账号补采
        </button>
      </nav>
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <template v-if="mode === 'content_supplement'">
        <AimaFeedbackBanner tone="info">
          按北京时间选择已入库笔记的发布时间范围，固定内容清单后补充详情和评论。
        </AimaFeedbackBanner>
        <section class="form-card">
          <label>内容发布时间 · 北京时间</label>
          <AimaDateRange
            :from="publishedFrom"
            :to="publishedTo"
            label="内容发布时间"
            :disabled="busy"
            @update:range="publishedRange = $event"
          />
          <small>包含开始日和结束日全天；无发布时间和 AI 明确判为不相关的内容不入选。</small>
        </section>
        <CollectionSupplementOptions :state="supplement" />
      </template>
      <template v-else>
        <AimaFeedbackBanner
          v-if="mode === 'discovery'"
          tone="info"
        >
          关键词包提供搜索词；内容入库前按冻结的品牌与车型目录过滤。
        </AimaFeedbackBanner>
        <section
          v-if="mode === 'discovery'"
          class="form-card"
        >
          <label>搜索条件 · 关键词包（至少选择一项）</label>
          <label
            v-for="pack in keywordPacks"
            :key="pack.id"
            class="pack-choice"
          ><input
            v-model="selectedPackIds"
            type="checkbox"
            :value="pack.id"
          ><span>{{ pack.name }}</span><small>{{ pack.keyword_count }} 词 · v{{ pack.version }}</small></label>
          <p v-if="keywordPacks.length === 0">
            当前没有可用的已启用词包。请先在“采集策略”创建并启用至少一个词包。
          </p>
        </section>
        <section
          v-if="mode === 'discovery'"
          class="form-card brand-card"
        >
          <fieldset>
            <legend>内容过滤条件 · 品牌</legend><label><input
              v-model="brandScope"
              type="radio"
              value="all_active"
            >全部启用品牌及车型</label><label><input
              v-model="brandScope"
              type="radio"
              value="selected"
            >指定品牌</label>
          </fieldset>
          <BrandMultiSelect
            v-if="brandScope === 'selected'"
            v-model="selectedBrandIds"
            label="指定品牌（可多选）"
          />
          <small
            v-if="brandScope === 'selected' && selectedBrandIds.length === 0"
            role="status"
          >请至少选择一个品牌，或改为全部启用品牌。</small>
        </section>
        <section
          v-if="mode === 'account_discovery'"
          class="form-card"
        >
          <label>账号作品发布时间 · 北京时间</label>
          <AimaDateRange
            :from="publishedFrom"
            :to="publishedTo"
            label="账号作品发布时间"
            :disabled="busy"
            @update:range="publishedRange = $event"
          />
          <small>包含开始日和结束日全天，遍历可访问作品。账号归属及日期符合的笔记都会入库。</small>
        </section>
        <section class="form-card">
          <label for="provider-select">采集渠道</label><select
            id="provider-select"
            v-model="providerConfigId"
          >
            <option value="">
              请选择采集渠道
            </option><option
              v-for="config in capabilities?.provider_configs"
              :key="config.id"
              :value="config.id"
            >
              {{ config.display_name }}
            </option>
          </select>
        </section>
        <section class="form-card platform-card">
          <label>目标平台与采集渠道</label>
          <div class="platform-grid">
            <div
              v-for="platform in availablePlatforms"
              :key="platform"
              class="platform-option"
              :class="{ selected: platforms.includes(platform) }"
            >
              <button
                type="button"
                :aria-pressed="platforms.includes(platform)"
                @click="togglePlatform(platform)"
              >
                <strong>{{ platformLabels[platform] }}</strong><span>{{ platforms.includes(platform) ? provider?.display_name : '点击选择' }}</span>
              </button>
              <CollectionSearchConfigFields
                v-if="mode === 'discovery' && platforms.includes(platform) && searchCapability(platform) && searchConfigByPlatform[platform]"
                :model-value="searchConfigByPlatform[platform]!"
                :capability="searchCapability(platform)!"
                :platform-label="platformLabels[platform]"
                @update:model-value="searchConfigByPlatform[platform] = $event"
              />
            </div>
          </div>
        </section>
        <section
          v-if="mode === 'account_discovery'"
          class="form-card account-fields"
        >
          <label>目标账号（每个已选平台至少一个，可添加多个）</label>
          <div
            v-for="platform in platforms"
            :key="platform"
            class="account-platform"
          >
            <strong>{{ platformLabels[platform] }}</strong>
            <div
              v-for="(account, index) in accounts"
              :key="index"
            >
              <div
                v-if="account.platform === platform"
                class="account-row"
              >
                <label>账号类型<select
                  v-model="account.account_id_type"
                  :disabled="busy"
                >
                  <option
                    v-for="idType in accountCapability(platform)?.supported_id_types"
                    :key="idType"
                    :value="idType"
                  >{{ accountIdLabels[idType] }}</option>
                </select></label>
                <label>账号 ID<input
                  v-model="account.account_id"
                  :aria-label="`${platformLabels[platform]}账号 ID`"
                  :disabled="busy"
                  maxlength="256"
                ></label>
                <label>昵称（可选）<input
                  v-model="account.nickname"
                  :aria-label="`${platformLabels[platform]}昵称`"
                  :disabled="busy"
                  maxlength="256"
                ></label>
                <AimaButton
                  variant="text"
                  size="small"
                  :disabled="busy"
                  @click="accounts.splice(index, 1)"
                >
                  删除账号
                </AimaButton>
              </div>
            </div>
            <AimaButton
              variant="secondary"
              size="small"
              :disabled="busy"
              @click="addAccount(platform)"
            >
              添加{{ platformLabels[platform] }}账号
            </AimaButton>
          </div>
          <small>按声明的 ID 精确核验账号；昵称用于辅助识别。重复账号、空 ID 或缺少平台账号时无法创建。</small>
        </section>
        <section class="form-card content-card">
          <label>采集内容</label><div class="content-options">
            <label><input
              type="checkbox"
              checked
              disabled
            > 内容详情</label><label><input
              v-model="includeComments"
              type="checkbox"
            > 评论</label><label><input
              v-model="includeSubComments"
              type="checkbox"
              :disabled="!includeComments"
            > 二级回复</label>
          </div>
        </section>
        <AimaFeedbackBanner tone="warning">
          默认采集全部可访问的一级评论和二级回复，可能增加请求次数、费用和耗时；可取消评论或二级回复。达到分页上限或接口不可访问时会标记采集缺口。
        </AimaFeedbackBanner>
        <AimaFeedbackBanner
          v-if="mode === 'account_discovery' && accountConfirmation && accountRequest?.account_selection"
          tone="warning"
          role="status"
        >
          即将采集 {{ platforms.length }} 个平台，共 {{ normalizedAccounts.length }} 个账号，发布时间 {{ publishedFrom }} 至 {{ publishedTo }}。
          {{ includeComments ? includeSubComments ? '包含全部可访问评论与二级回复。' : '包含全部可访问一级评论。' : '仅采集作品详情。' }}
          请求次数取决于作品与评论分页，会产生接口费用。确认后创建任务。
        </AimaFeedbackBanner>
      </template>
    </div>
    <template #footer>
      <footer class="dialog-footer">
        <AimaButton
          variant="secondary"
          size="small"
          :disabled="busy"
          @click="emit('update:modelValue', false)"
        >
          取消
        </AimaButton><AimaButton
          variant="primary"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ busy ? '创建中…' : mode === 'account_discovery' ? accountConfirmation ? '确认创建账号任务' : '核对账号与费用' : '创建补采任务' }}
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>
</template>
<style scoped>
.dialog-header { display: flex; height: 76px; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--aima-border); background: var(--aima-surface); }
.dialog-header strong, .dialog-header span { display: block; }
.dialog-header strong { color: var(--aima-text); font-size: 18px; font-weight: 700; line-height: 24px; }
.dialog-header span { margin-top: 4px; color: var(--aima-color-text-tertiary); font-size: 12px; line-height: 18px; }
.dialog-body { display: flex; min-height: 0; flex-direction: column; gap: 20px; padding: 16px 24px 12px; }
.mode-tabs { display: flex; min-height: 40px; gap: 8px; }
.mode-tabs button { min-height: 40px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; color: var(--aima-text-muted); background: transparent; cursor: pointer; font-size: 13px; line-height: 20px; }
.mode-tabs button.active { border-bottom-color: var(--aima-primary); color: var(--aima-primary); font-weight: 500; }
.form-card { padding: 10px 11px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.form-card > label, .section-title-row > label { display: block; margin-bottom: 9px; color: var(--aima-text); font-size: 13px; font-weight: 500; line-height: 20px; }
select { width: 100%; height: 32px; padding: 0 12px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); color: var(--aima-text-secondary); background: var(--aima-surface); font-size: 13px; }
select:disabled { color: var(--aima-text-secondary); opacity: 1; }
.pack-choice-list { display: grid; gap: 4px; }
.pack-choice { display: grid; min-height: 32px; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.pack-choice input, .content-option input { accent-color: var(--aima-primary); }
.pack-choice small { color: var(--aima-text-disabled); font-size: 11px; }
.section-title-row { display: flex; align-items: center; gap: 12px; }
.section-title-row > label { margin-bottom: 0; }
.section-title-row small { color: var(--aima-text-disabled); font-size: 11px; }
.platform-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.platform-option { padding: 10px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); background: var(--aima-surface); }
.platform-option.selected { border-color: var(--aima-primary); background: var(--aima-color-primary-light); }
.platform-option.unavailable { background: var(--aima-surface-muted); }
.platform-option button { display: flex; width: 100%; min-height: 38px; align-items: center; justify-content: space-between; gap: 12px; padding: 0; border: 0; color: var(--aima-text-secondary); background: transparent; cursor: pointer; font-size: 12px; text-align: left; }
.platform-option strong, .platform-option small { display: block; }
.platform-option strong { color: var(--aima-text); font-size: 14px; font-weight: 500; line-height: 22px; }
.platform-option small { margin-top: 5px; color: var(--aima-text-disabled); font-size: 11px; }
.platform-option button > span + span { color: var(--aima-text-muted); font-size: 11px; }
.platform-search-fields { margin-top: 12px; }
.brand-card { min-height: 114px; }
.account-platform { display: grid; gap: 8px; margin: 12px 0; }
.account-row { display: grid; grid-template-columns: 130px minmax(0, 1fr) minmax(0, 1fr) auto; align-items: end; gap: 8px; }
.account-row label { color: var(--aima-text-secondary); font-size: 12px; }
.account-row input { box-sizing: border-box; width: 100%; height: 32px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); padding: 0 8px; background: var(--aima-surface); color: var(--aima-text); }
.brand-card fieldset { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 0 0 12px; padding: 0; border: 0; }
.brand-card legend { width: 100%; margin-bottom: 2px; color: var(--aima-text); font-size: 13px; font-weight: 500; }
.brand-card fieldset label { display: inline-flex; align-items: center; gap: 5px; color: var(--aima-text-secondary); font-size: 12px; }
.brand-card > small { display: block; margin-top: 8px; color: var(--aima-text-muted); font-size: 11px; }
.platform-state { margin: 8px 0 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.content-options { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 16px; }
.content-option { display: grid; min-height: 32px; grid-template-columns: 16px 1fr auto; align-items: center; gap: 8px; color: var(--aima-text-secondary); font-size: 13px; }
.content-option small { color: var(--aima-text-disabled); font-size: 11px; }
.content-option.disabled { color: var(--aima-text-disabled); }
.dialog-footer { display: flex; height: 72px; align-items: center; justify-content: flex-end; gap: 10px; padding: 0 24px; border-top: 1px solid var(--aima-border); background: var(--aima-surface); }
.dialog-footer :deep(.aima-button.is-primary) { min-width: 136px; }
.dialog-footer :deep(.aima-button.is-secondary) { min-width: 88px; }
@media (max-width: 600px) { .platform-grid, .content-options, .account-row { grid-template-columns: 1fr; } .section-title-row { flex-wrap: wrap; } }
</style>
