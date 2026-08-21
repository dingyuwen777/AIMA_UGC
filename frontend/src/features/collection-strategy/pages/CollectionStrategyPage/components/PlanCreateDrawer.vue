<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type {
  CollectionCapabilitiesResponse,
  CollectionPlanCreateRequest,
  CollectionPlatform,
  KeywordPackSummaryResponse,
} from '../../../../../generated/api/client'

const props = defineProps<{
  packs: KeywordPackSummaryResponse[]
  capabilities: CollectionCapabilitiesResponse | null
  relevanceName: string
  saving: boolean
}>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ submit: [request: CollectionPlanCreateRequest] }>()

const platformOptions: { value: CollectionPlatform; label: string }[] = [
  { value: 'xhs', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'weibo', label: '微博' },
  { value: 'bilibili', label: 'B站' },
  { value: 'kuaishou', label: '快手' },
]
const name = ref('')
const scheduleExpr = ref('0 9 * * *')
const enabled = ref(true)
const selectedPacks = ref<string[]>([])
const providerByPlatform = reactive<Partial<Record<CollectionPlatform, string>>>({})

const selectedPlatforms = computed(() =>
  platformOptions.filter((item) => providerByPlatform[item.value]),
)

watch(open, (value) => {
  if (!value) return
  name.value = ''
  scheduleExpr.value = '0 9 * * *'
  enabled.value = true
  selectedPacks.value = []
  for (const option of platformOptions) delete providerByPlatform[option.value]
})

function configsFor(platform: CollectionPlatform) {
  const providers = new Set(
    (props.capabilities?.capabilities ?? [])
      .filter((item) => item.platform === platform && item.operations.includes('keyword_search'))
      .map((item) => item.provider),
  )
  return (props.capabilities?.provider_configs ?? []).filter((item) => providers.has(item.provider))
}

function togglePlatform(platform: CollectionPlatform): void {
  if (providerByPlatform[platform]) {
    delete providerByPlatform[platform]
    return
  }
  const first = configsFor(platform)[0]
  if (first) providerByPlatform[platform] = first.id
}

function submit(): void {
  if (!name.value.trim() || !scheduleExpr.value.trim()) return
  if (selectedPacks.value.length === 0 || selectedPlatforms.value.length === 0) return
  emit('submit', {
    name: name.value.trim(),
    schedule_expr: scheduleExpr.value.trim(),
    keyword_pack_ids: selectedPacks.value,
    platforms: selectedPlatforms.value.map((item) => ({
      platform: item.value,
      provider_config_id: providerByPlatform[item.value]!,
    })),
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
        <div><h2>新建采集计划</h2><p>保存 Discovery 词包与正式周期调度配置</p></div><button
          type="button"
          aria-label="关闭"
          @click="open = false"
        >
          ×
        </button>
      </header>
      <div class="body">
        <label><strong>1. 计划名称</strong><input
          v-model="name"
          maxlength="200"
          placeholder="例如：爱玛新品口碑追踪"
        ></label>
        <fieldset>
          <legend>2. Discovery 词包</legend><label
            v-for="pack in packs"
            :key="pack.id"
            class="check"
          ><input
            v-model="selectedPacks"
            type="checkbox"
            :value="pack.id"
          >{{ pack.name }} · v{{ pack.version }}</label><p v-if="packs.length === 0">
            请先创建启用且非空的 Discovery 词包。
          </p>
        </fieldset>
        <fieldset>
          <legend>3. 目标平台与 Provider</legend><div class="platforms">
            <div
              v-for="option in platformOptions"
              :key="option.value"
              :class="['platform', { active: providerByPlatform[option.value] }]"
              role="button"
              tabindex="0"
              @click="togglePlatform(option.value)"
              @keydown.enter="togglePlatform(option.value)"
            >
              <span>{{ option.label }}</span><select
                v-if="providerByPlatform[option.value]"
                v-model="providerByPlatform[option.value]"
                @click.stop
              >
                <option
                  v-for="config in configsFor(option.value)"
                  :key="config.id"
                  :value="config.id"
                >
                  {{ config.display_name }}
                </option>
              </select><small v-else>{{ configsFor(option.value).length ? '点击选择' : '暂无可用配置' }}</small>
            </div>
          </div>
        </fieldset>
        <label><strong>4. 周期调度</strong><span class="cron"><input
          v-model="scheduleExpr"
          maxlength="100"
          aria-label="Cron 表达式"
        ><em>Asia/Shanghai</em></span><small>首版使用五字段 Cron；一次性主动发现请前往采集运行中心。</small></label>
        <div class="policy">
          <strong>5. 固定采集策略</strong><div><span>内容详情<b>变化时</b></span><span>评论<b>自适应</b></span></div>
        </div>
        <div class="relevance">
          <strong>◎ 全局相关性（系统全局，不可覆盖）</strong><span>{{ relevanceName || '尚未配置' }}</span><small>创建启用 Plan 前，后端会再次验证全局 Relevance。</small>
        </div>
        <label class="switch"><strong>6. 创建后启用计划</strong><input
          v-model="enabled"
          type="checkbox"
        ></label>
        <div class="warning">
          ⚠ 计划执行会发起真实 TikHub 请求并可能产生费用；当前不提供预算或金额上限。
        </div>
      </div>
      <footer>
        <button
          type="button"
          @click="open = false"
        >
          取消
        </button><button
          class="primary"
          type="button"
          :disabled="saving || !name.trim() || !scheduleExpr.trim() || selectedPacks.length === 0 || selectedPlatforms.length === 0"
          @click="submit"
        >
          {{ saving ? '保存中…' : '保存采集计划' }}
        </button>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 100; inset: 0; background: rgb(20 29 44 / 34%); }
aside { position: absolute; top: 0; right: 0; display: flex; width: 510px; height: 100%; flex-direction: column; background: #fff; box-shadow: -10px 0 30px rgb(20 29 44 / 12%); }
header { display: flex; min-height: 84px; align-items: center; justify-content: space-between; padding: 18px 24px; border-bottom: 1px solid var(--aima-border); }header h2 { margin: 0; font-size: 20px; }header p { margin: 6px 0 0; color: #737e91; font-size: 13px; }header button { border: 0; color: #4d586a; background: transparent; font-size: 28px; cursor: pointer; }
.body { flex: 1; overflow: auto; padding: 22px 24px; }label,fieldset,.policy,.relevance { display: block; margin: 0 0 22px; }label strong,legend,.policy > strong { display: block; margin-bottom: 9px; color: #253044; font-size: 14px; }input:not([type='checkbox']),select { width: 100%; height: 40px; padding: 0 11px; border: 1px solid #d9dee8; border-radius: 6px; background: #fff; }fieldset { padding: 0; border: 0; }.check { display: inline-flex; align-items: center; gap: 6px; margin: 0 12px 8px 0; padding: 8px 10px; border: 1px solid #dfe4ec; border-radius: 6px; font-size: 13px; }
.platforms { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }.platform { min-height: 78px; padding: 10px; border: 1px solid #dfe4ec; border-radius: 7px; cursor: pointer; }.platform.active { border-color: var(--aima-primary); background: #fff5f8; }.platform span,.platform small { display: block; }.platform span { color: #263146; font-weight: 600; }.platform small { margin-top: 8px; color: #818b9d; }.platform select { height: 30px; margin-top: 7px; font-size: 11px; }
.cron { display: flex; align-items: center; border: 1px solid #d9dee8; border-radius: 6px; }.cron input { border: 0 !important; }.cron em { padding: 0 10px; color: #576276; font-size: 12px; font-style: normal; white-space: nowrap; }label > small,.relevance small { display: block; margin-top: 7px; color: #8590a2; }
.policy > div { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.policy span { padding: 12px; border: 1px solid #e0e4eb; border-radius: 7px; color: #6a7588; }.policy b { display: block; margin-top: 5px; color: #263146; }
.relevance { padding: 13px; border: 1px solid #bee6d2; border-radius: 7px; color: #167d50; background: #f0faf5; }.relevance strong,.relevance span { display: block; }.relevance span { margin-top: 6px; font-weight: 600; }
.switch { display: flex; align-items: center; justify-content: space-between; }.switch strong { margin: 0; }.switch input { width: 20px; height: 20px; accent-color: var(--aima-primary); }.warning { padding: 12px; border: 1px solid #ffd2a3; border-radius: 7px; color: #b75c06; background: #fff8ef; font-size: 13px; }
footer { display: flex; gap: 12px; padding: 16px 24px; border-top: 1px solid var(--aima-border); }footer button { height: 42px; flex: 1; border: 1px solid #d9dee7; border-radius: 7px; background: #fff; cursor: pointer; }.primary { border-color: var(--aima-primary) !important; color: #fff; background: var(--aima-primary) !important; }.primary:disabled { opacity: .5; cursor: default; }
</style>
