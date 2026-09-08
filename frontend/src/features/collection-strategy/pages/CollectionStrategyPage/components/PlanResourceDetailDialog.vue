<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { KeywordPackResponse, KeywordPackSummaryResponse, VehicleModelResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { fetchPack, fetchVehicle } from '../../../api'
import { collectionPlatformLabel, formatBeijingDateTime } from '../../../presentation'

const props = defineProps<{
  resource: { kind: 'pack' | 'vehicle'; id: string } | null
  packs: KeywordPackSummaryResponse[]
  vehicles: VehicleModelResponse[]
}>()
const emit = defineEmits<{ close: [] }>()
const open = computed({ get: () => props.resource !== null, set: (value: boolean) => { if (!value) emit('close') } })
const pack = ref<KeywordPackResponse | null>(null)
const vehicle = ref<VehicleModelResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let requestVersion = 0

/** 每次打开重新读取当前配置；关闭或切换后，旧请求不能改写新详情。 */
async function load(): Promise<void> {
  const version = ++requestVersion
  const resource = props.resource
  pack.value = null
  vehicle.value = null
  error.value = null
  loading.value = resource !== null
  if (!resource) return
  try {
    if (resource.kind === 'pack') {
      const result = await fetchPack(resource.id)
      if (version === requestVersion) pack.value = result
    } else {
      const result = await fetchVehicle(resource.id)
      if (version === requestVersion) vehicle.value = result
    }
  } catch (reason) {
    if (version === requestVersion) error.value = reason instanceof Error ? reason.message : '无法读取资源详情，请重试。'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

watch(() => props.resource, load, { immediate: true })
</script>

<template>
  <AimaDialog
    v-model="open"
    :label="resource?.kind === 'vehicle' ? '车型详情' : '关键词包详情'"
    width="630px"
    class="plan-resource-dialog"
  >
    <template #header>
      <div><h2>{{ resource?.kind === 'vehicle' ? '车型详情' : '关键词包详情' }}</h2><p>当前配置 · 每次运行会另行冻结当时使用的配置</p></div>
      <AimaButton
        variant="text"
        aria-label="关闭"
        @click="emit('close')"
      >
        关闭
      </AimaButton>
    </template>
    <div class="resource-body">
      <p
        v-if="loading"
        role="status"
      >
        正在读取完整配置…
      </p>
      <AimaFeedbackBanner
        v-else-if="error"
        tone="error"
        role="alert"
      >
        {{ error }} <AimaButton
          size="small"
          @click="load"
        >
          重试
        </AimaButton>
      </AimaFeedbackBanner>
      <template v-else-if="pack">
        <h3>{{ pack.name }} <small>v{{ pack.version }} · {{ pack.enabled ? '已启用' : '已停用' }}</small></h3>
        <p class="description">
          {{ pack.description || '暂无描述' }}
        </p>
        <h4>全部关键词（{{ pack.keywords.length }}）</h4>
        <table v-if="pack.keywords.length">
          <thead><tr><th>关键词</th><th>适用平台</th><th>优先级</th><th>状态</th><th>备注</th></tr></thead>
          <tbody>
            <tr
              v-for="item in pack.keywords"
              :key="`${item.id}-${item.platform_scope}`"
            >
              <td>{{ item.text }}</td><td>{{ item.platform_scope && item.platform_scope !== 'all' ? collectionPlatformLabel(item.platform_scope) : '全部平台' }}</td><td>{{ item.priority }}</td><td>{{ item.enabled ? '已启用' : '已停用' }}</td><td>{{ item.note || '无' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else>
          当前词包没有关键词。
        </p>
        <details>
          <summary>技术详情</summary><p>词包标识：{{ pack.id }}</p><p
            v-for="item in pack.keywords"
            :key="`${item.id}-${item.platform_scope}`"
          >
            {{ item.text }}：{{ item.id }}
          </p>
        </details>
      </template>
      <template v-else-if="vehicle">
        <h3>{{ vehicle.display_name }} <small>v{{ vehicle.version }}</small></h3>
        <dl>
          <div><dt>车型编码</dt><dd>{{ vehicle.code }}</dd></div>
          <div><dt>状态</dt><dd>{{ vehicle.status === 'active' ? '已启用' : vehicle.status === 'deprecated' ? '已停用' : '已合并' }}</dd></div>
          <div><dt>系列</dt><dd>{{ vehicle.series_name || '未设置' }}</dd></div>
          <div><dt>分类</dt><dd>{{ vehicle.category_name || '未设置' }}</dd></div>
          <div><dt>目录版本</dt><dd>v{{ vehicle.catalog_version }}</dd></div>
          <div><dt>业务引用</dt><dd>{{ vehicle.referenced ? '已被引用' : '尚未引用' }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ formatBeijingDateTime(vehicle.created_at) }}</dd></div>
          <div><dt>最近更新</dt><dd>{{ formatBeijingDateTime(vehicle.updated_at) }}</dd></div>
          <div v-if="vehicle.merged_into_id">
            <dt>合并至</dt><dd>{{ vehicles.find((item) => item.id === vehicle?.merged_into_id)?.display_name || '目标车型不在当前目录' }}</dd>
          </div>
        </dl>
        <h4>全部别名（{{ vehicle.aliases?.length ?? 0 }}）</h4>
        <ul v-if="vehicle.aliases?.length">
          <li
            v-for="alias in vehicle.aliases"
            :key="alias.id"
          >
            {{ alias.text }}
          </li>
        </ul><p v-else>
          未设置别名。
        </p>
        <h4>关联词包（{{ vehicle.keyword_pack_ids?.length ?? 0 }}）</h4>
        <ul v-if="vehicle.keyword_pack_ids?.length">
          <li
            v-for="id in vehicle.keyword_pack_ids"
            :key="id"
          >
            {{ packs.find((item) => item.id === id)?.name || '历史词包（当前目录不可用）' }}
          </li>
        </ul><p v-else>
          未关联词包。
        </p>
        <details>
          <summary>技术详情</summary><p>车型标识：{{ vehicle.id }}</p><p v-if="vehicle.merged_into_id">
            合并目标标识：{{ vehicle.merged_into_id }}
          </p><p
            v-for="id in vehicle.keyword_pack_ids"
            :key="id"
          >
            词包标识：{{ id }}
          </p><p
            v-for="alias in vehicle.aliases"
            :key="alias.id"
          >
            别名标识：{{ alias.id }} · 标准化文本：{{ alias.normalized_text }}
          </p>
        </details>
      </template>
    </div>
    <template #footer>
      <AimaButton @click="emit('close')">
        返回计划详情
      </AimaButton>
    </template>
  </AimaDialog>
</template>

<style scoped>
:global(.plan-resource-dialog) { height: 526px; border: 0; border-radius: 10px; }
:global(.plan-resource-dialog > .aima-dialog-header) { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 24px 24px 0; }
:global(.plan-resource-dialog > .aima-dialog-body) { flex: 1; }
:global(.plan-resource-dialog > .aima-dialog-footer) { display: flex; justify-content: flex-end; padding: 20px 24px 24px; }
h2 { margin: 0; font-size: 19px; line-height: 22px; }h2 + p { margin: 5px 0 0; color: #788397; font-size: 12px; line-height: 16px; }.resource-body { padding: 20px 24px 0; font-size: 13px; overflow-wrap: anywhere; }h3 { margin: 0 0 10px; font-size: 17px; }h3 small { display: block; margin-top: 6px; color: #788397; font-size: 12px; font-weight: 400; }.description { white-space: pre-wrap; color: #536075; }h4 { margin: 18px 0 8px; font-size: 13px; }table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 12px; }th,td { padding: 9px 7px; border: 1px solid var(--aima-border); text-align: left; vertical-align: top; }th { background: #f7f9fc; font-weight: 500; }th:first-child { width: 26%; }th:nth-child(2) { width: 18%; }th:nth-child(3),th:nth-child(4) { width: 13%; }dl { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }dl > div { padding: 10px; border: 1px solid var(--aima-border); border-radius: 6px; }dt { color: #788397; font-size: 12px; }dd { margin: 6px 0 0; }ul { margin: 0; padding-left: 20px; }li { margin-top: 6px; }details { margin-top: 20px; padding: 10px; border: 1px dashed var(--aima-border); color: #788397; font-size: 11px; }summary { cursor: pointer; }
</style>
