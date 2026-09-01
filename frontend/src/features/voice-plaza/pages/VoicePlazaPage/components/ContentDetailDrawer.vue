<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  AnalysisManualLabelRequest,
  ContentAnalysisManualReviewRequest,
  ContentAnalysisTaxonomyResponse,
  ContentDetailResponse,
} from '../../../../../generated/api/client'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { contentSummary, formatDateTime, formatNumber, labelPairText, platformLabel } from '../../../format'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item: ContentDetailResponse | null
  loading: boolean
  taxonomy?: ContentAnalysisTaxonomyResponse | null
  saving?: boolean
}>(), { taxonomy: null, saving: false })
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  'review-vehicles': [vehicleModelIds: string[], unlockExisting: boolean]
  'review-analysis': [request: Omit<ContentAnalysisManualReviewRequest, 'content_version'>]
}>()

const vehicleModelIds = ref<string[]>([])
const voiceType = ref('')
const sentiment = ref('')
const labels = ref<AnalysisManualLabelRequest[]>([])
const labelPrimary = ref('')
const labelSecondary = ref('')
const confirmUnlockVehicles = ref(false)
const confirmUnlockAnalysis = ref(false)

const hasVehicleLock = computed(() =>
  (props.item?.vehicles ?? []).some((vehicle) =>
    vehicle.evidences.some((evidence) => evidence.is_manual_locked),
  ),
)
const lockedDimensions = computed(() => props.item?.analysis.manual_locked_dimensions ?? [])
const secondaryOptions = computed(() =>
  props.taxonomy?.labels.find((item) => item.primary_label === labelPrimary.value)?.secondary_labels ?? [],
)

watch(() => props.item, (item) => {
  vehicleModelIds.value = (item?.vehicles ?? []).map((vehicle) => vehicle.vehicle_model_id)
  voiceType.value = item?.analysis.voice_type ?? ''
  sentiment.value = item?.analysis.sentiment ?? ''
  labels.value = [...(item?.analysis.labels ?? [])]
  confirmUnlockVehicles.value = false
  confirmUnlockAnalysis.value = false
}, { immediate: true })

function addLabel(): void {
  if (!labelPrimary.value || !labelSecondary.value) return
  if (!labels.value.some((item) => item.primary_label === labelPrimary.value && item.secondary_label === labelSecondary.value)) {
    labels.value.push({ primary_label: labelPrimary.value, secondary_label: labelSecondary.value })
  }
  labelSecondary.value = ''
}

function saveVehicleReview(): void {
  emit('review-vehicles', vehicleModelIds.value, hasVehicleLock.value && confirmUnlockVehicles.value)
}

function unlockVehicleReview(): void {
  if (!window.confirm('解除车型人工锁定后，当前自动证据会重新生效。是否继续？')) return
  emit('review-vehicles', [], true)
}

function saveAnalysisReview(): void {
  if (!voiceType.value || !sentiment.value || labels.value.length === 0) return
  emit('review-analysis', {
    voice_type: voiceType.value,
    sentiment: sentiment.value,
    labels: labels.value,
    unlock_dimensions: confirmUnlockAnalysis.value ? [...lockedDimensions.value] : [],
  })
}

function unlockAnalysisReview(): void {
  if (!window.confirm('解除人工分析锁定后，页面将恢复展示当前 AI 结果。是否继续？')) return
  emit('review-analysis', { unlock_dimensions: [...lockedDimensions.value] })
}

/** 将内容补充状态映射为用户可理解的区块标题。 */
function supplementTitle(status: string): string {
  if (status === 'failed') return '内容补充失败'
  if (status === 'partial_success') return '内容补充不完整'
  if (status === 'cancelled') return '内容补充已取消'
  return '内容补充进行中'
}

/** 解释内容补充的真实状态，并保留进入采集中心继续处理的语义。 */
function supplementMessage(status: string): string {
  if (status === 'failed') {
    return '暂时无法获取完整详情与评论。已保留原始导入内容，可在采集中心查看失败原因并重新发起补充。'
  }
  if (status === 'partial_success') {
    return '已获取部分详情或评论，仍有部分数据未成功补充。可在采集中心查看结果并按需重试。'
  }
  if (status === 'cancelled') {
    return '内容补充已取消，当前展示已入库内容。可在采集中心重新发起补充。'
  }
  return '正在补充完整详情与评论，当前先展示已入库内容。'
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="drawer-layer"
    >
      <button
        class="backdrop"
        type="button"
        aria-label="关闭内容详情"
        @click="$emit('update:modelValue', false)"
      />
      <aside
        class="drawer"
        aria-label="内容详情"
      >
        <header>
          <div>
            <h2>内容详情</h2>
            <small v-if="item">Content ID: {{ item.id }}</small>
          </div>
          <button
            class="close-button"
            type="button"
            aria-label="关闭"
            @click="$emit('update:modelValue', false)"
          >
            <AimaIcon
              name="close"
              :size="22"
            />
          </button>
        </header>
        <div
          v-if="loading && !item"
          class="drawer-state"
        >
          正在加载详情…
        </div>
        <div
          v-else-if="item"
          class="drawer-body"
        >
          <section class="hero">
            <div class="badges">
              <span class="platform">{{ platformLabel(item.platform) }}</span>
              <span class="analysis">{{ item.analysis.status === 'completed' ? item.analysis.sentiment || '已打标' : item.analysis.status === 'stale' ? '需重新打标' : '未打标' }}</span>
            </div>
            <h3>{{ contentSummary(item.title, item.text) }}</h3>
            <p>{{ item.text || '该内容没有正文。' }}</p>
            <a
              v-if="item.content_url"
              :href="item.content_url"
              target="_blank"
              rel="noopener noreferrer"
            >查看原始链接 ↗</a>
          </section>

          <section
            v-if="item.supplement_status && item.supplement_status.status !== 'succeeded'"
            class="supplement-status"
            :class="`supplement-status--${item.supplement_status.status}`"
          >
            <h4>{{ supplementTitle(item.supplement_status.status) }}</h4>
            <p>{{ supplementMessage(item.supplement_status.status) }}</p>
          </section>

          <section>
            <h4>AI 情感与全部标签</h4>
            <p class="analysis-summary">
              <span>发声类型：{{ item.analysis.voice_type || '未判定' }}</span>
              <span>情感：{{ item.analysis.sentiment || '未判定' }}</span>
            </p>
            <div class="label-grid">
              <span
                v-for="(label, index) in item.analysis.labels ?? []"
                :key="`${label.primary_label}:${label.secondary_label}:${index}`"
              >{{ labelPairText(label).replace(' / ', ' ／ ') }}</span>
              <em v-if="(item.analysis.labels ?? []).length === 0">暂无 AI 标签</em>
            </div>
            <small v-if="item.analysis.analyzed_at">分析时间：{{ formatDateTime(item.analysis.analyzed_at) }} · {{ item.analysis.model_provider }} / {{ item.analysis.model }}</small>
          </section>

          <section class="manual-review">
            <header class="section-heading">
              <div><h4>车型人工确认</h4><small>0..N 个车型；自动别名证据与人工结论分开保留。</small></div>
              <span v-if="hasVehicleLock">已人工锁定</span>
            </header>
            <VehicleMultiSelect
              v-model="vehicleModelIds"
              label="当前车型"
            />
            <div
              v-if="(item.vehicles ?? []).length"
              class="evidence-list"
            >
              <article
                v-for="vehicle in item.vehicles ?? []"
                :key="vehicle.vehicle_model_id"
              >
                <strong>{{ vehicle.display_name }}</strong>
                <span
                  v-for="(evidence, index) in vehicle.evidences"
                  :key="`${evidence.source}:${index}`"
                >
                  {{ evidence.source }}<template v-if="evidence.matched_text"> · “{{ evidence.matched_text }}”</template> · catalog v{{ evidence.catalog_version }}<template v-if="evidence.is_manual_locked"> · 人工锁定</template>
                </span>
              </article>
            </div>
            <label
              v-if="hasVehicleLock"
              class="unlock-confirm"
            ><input
              v-model="confirmUnlockVehicles"
              type="checkbox"
            >我确认先解锁现有人工车型结论，再保存新结论</label>
            <div class="review-actions">
              <AimaButton
                v-if="hasVehicleLock"
                size="small"
                @click="unlockVehicleReview"
              >
                仅解除锁定
              </AimaButton><AimaButton
                variant="primary"
                size="small"
                :disabled="saving || (hasVehicleLock && !confirmUnlockVehicles)"
                @click="saveVehicleReview"
              >
                保存车型结论
              </AimaButton>
            </div>
          </section>

          <section class="manual-review">
            <header class="section-heading">
              <div><h4>发声类型、情感与标签人工纠正</h4><small>合法值来自当前发布的原子 Analysis Scheme。</small></div>
              <span v-if="lockedDimensions.length">锁定 {{ lockedDimensions.join('、') }}</span>
            </header>
            <p
              v-if="item.analysis.status !== 'completed'"
              class="review-warning"
            >
              尚无可纠正的当前 AI 结果，请先完成 AI 打标。
            </p>
            <template v-else>
              <div class="review-grid">
                <label>发声类型<select v-model="voiceType"><option value="">请选择</option><option
                  v-for="value in taxonomy?.voice_types ?? []"
                  :key="value"
                  :value="value"
                >{{ value }}</option></select></label>
                <label>情感<select v-model="sentiment"><option value="">请选择</option><option
                  v-for="value in taxonomy?.sentiments ?? []"
                  :key="value"
                  :value="value"
                >{{ value }}</option></select></label>
              </div>
              <div class="label-editor">
                <select
                  v-model="labelPrimary"
                  @change="labelSecondary = ''"
                >
                  <option value="">
                    一级标签
                  </option><option
                    v-for="group in taxonomy?.labels ?? []"
                    :key="group.primary_label"
                    :value="group.primary_label"
                  >
                    {{ group.primary_label }}
                  </option>
                </select>
                <select
                  v-model="labelSecondary"
                  :disabled="!labelPrimary"
                >
                  <option value="">
                    二级标签
                  </option><option
                    v-for="value in secondaryOptions"
                    :key="value"
                    :value="value"
                  >
                    {{ value }}
                  </option>
                </select>
                <AimaButton
                  size="small"
                  :disabled="!labelPrimary || !labelSecondary"
                  @click="addLabel"
                >
                  添加
                </AimaButton>
              </div>
              <div class="manual-labels">
                <button
                  v-for="(label, index) in labels"
                  :key="`${label.primary_label}:${label.secondary_label}`"
                  type="button"
                  @click="labels.splice(index, 1)"
                >
                  {{ label.primary_label }} ／ {{ label.secondary_label }} ×
                </button>
              </div>
              <label
                v-if="lockedDimensions.length"
                class="unlock-confirm"
              ><input
                v-model="confirmUnlockAnalysis"
                type="checkbox"
              >我确认先解锁已锁定维度，再保存新的人工结论</label>
              <div class="review-actions">
                <AimaButton
                  v-if="lockedDimensions.length"
                  size="small"
                  @click="unlockAnalysisReview"
                >
                  解除全部分析锁定
                </AimaButton><AimaButton
                  variant="primary"
                  size="small"
                  :disabled="saving || !taxonomy || !voiceType || !sentiment || labels.length === 0 || (lockedDimensions.length > 0 && !confirmUnlockAnalysis)"
                  @click="saveAnalysisReview"
                >
                  保存人工纠正
                </AimaButton>
              </div>
            </template>
          </section>

          <section>
            <h4>第三方可用状态</h4>
            <p v-if="item.availability">
              {{ item.availability.status }} · {{ item.availability.reason_code }} · {{ item.availability.evidence_kind }} · {{ formatDateTime(item.availability.observed_at) }}
            </p>
            <p v-else>
              unknown · 尚无明确 Provider 证据。技术失败不会直接标记为确认下架。
            </p>
          </section>

          <section v-if="(item.media ?? []).length > 0">
            <h4>原始内容媒体</h4>
            <div class="media-grid">
              <a
                v-for="media in item.media ?? []"
                :key="`${media.position}:${media.url}`"
                :href="media.url || undefined"
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  v-if="media.preview_url"
                  :src="media.preview_url"
                  :alt="media.alt_text || '原始内容媒体预览'"
                >
                <span v-else>{{ media.media_type }} · 查看原始媒体</span>
              </a>
            </div>
          </section>

          <section>
            <h4>结构化信息</h4>
            <dl>
              <div><dt>平台</dt><dd>{{ platformLabel(item.platform) }}</dd></div>
              <div><dt>作者</dt><dd>{{ item.author_display_name || '未知' }}</dd></div>
              <div><dt>内容类型</dt><dd>{{ item.content_type }}</dd></div>
              <div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div>
              <div><dt>外部内容 ID</dt><dd>{{ item.external_content_id }}</dd></div>
              <div><dt>来源</dt><dd>{{ item.source.provider_name }}</dd></div>
            </dl>
          </section>

          <section>
            <h4>互动数据</h4>
            <div class="metric-grid">
              <span>点赞<b>{{ formatNumber(item.metrics.like_count) }}</b></span>
              <span>评论<b>{{ formatNumber(item.metrics.comment_count) }}</b></span>
              <span>分享<b>{{ formatNumber(item.metrics.share_count) }}</b></span>
              <span>收藏<b>{{ formatNumber(item.metrics.favorite_count) }}</b></span>
              <span>播放<b>{{ formatNumber(item.metrics.play_count) }}</b></span>
              <span>浏览<b>{{ formatNumber(item.metrics.view_count) }}</b></span>
            </div>
          </section>

          <section>
            <h4>评论与覆盖</h4>
            <p
              v-if="item.comment_coverage"
              class="coverage"
            >
              已采集 {{ formatNumber(item.comment_coverage.collected_count) }} / {{ formatNumber(item.comment_coverage.reported_total) }}，覆盖状态：{{ item.comment_coverage.coverage }}
            </p>
            <div
              v-if="(item.comments ?? []).length"
              class="comments"
            >
              <article
                v-for="comment in item.comments ?? []"
                :key="comment.id"
              >
                <strong>{{ comment.author_display_name || '匿名用户' }}</strong>
                <time>{{ formatDateTime(comment.published_at) }}</time>
                <p>{{ comment.text || '无评论正文' }}</p>
              </article>
            </div>
            <p
              v-else
              class="empty"
            >
              暂无已入库评论。
            </p>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; z-index: 100; inset: 0; }
.backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgb(25 32 45 / 46%); }
.drawer { position: absolute; top: 0; right: 0; display: flex; width: min(610px, 100vw); height: 100%; flex-direction: column; background: var(--aima-surface); box-shadow: -12px 0 36px rgb(31 39 55 / 12%); }
header { display: flex; min-height: 82px; flex: none; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--aima-border); }
header h2 { margin: 0 0 5px; color: var(--aima-text); font-size: 20px; line-height: 28px; }
header small { color: var(--aima-text-disabled); font-size: 10px; }
.close-button { display: grid; width: 34px; height: 34px; place-items: center; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.drawer-body { display: grid; overflow-y: auto; gap: 12px; padding: 20px 24px 28px; }
.drawer-body > section { margin: 0; padding: 12px 14px; border: 1px solid var(--aima-border); border-radius: 8px; background: var(--aima-surface); }
.drawer-body > .hero { display: grid; gap: 10px; padding: 0 0 12px; border: 0; }
.badges { display: flex; gap: 8px; }
.badges span { padding: 3px 8px; border-radius: 4px; font-size: 11px; }
.platform { color: #2765a3; background: #e8f3ff; }
.analysis { color: #cc2f58; background: var(--aima-primary-soft); }
.hero h3 { margin: 0; color: var(--aima-text); font-size: 18px; line-height: 27px; }
.hero p,
.drawer-body section p { margin: 0; color: var(--aima-text-muted); font-size: 12px; line-height: 18px; }
.hero a { color: var(--aima-primary); font-size: 11px; font-weight: 500; text-decoration: none; }
.drawer-body > .supplement-status { border-color: #dfe5ee; background: #f7f9fc; }
.supplement-status h4 { margin-bottom: 6px; }
.drawer-body > .supplement-status--failed { border-color: #f0cbd0; background: #fff7f8; }
.drawer-body > .supplement-status--partial_success { border-color: #eadbbd; background: #fffbf2; }
.drawer-body > .supplement-status--running,
.drawer-body > .supplement-status--queued { border-color: #ccdeef; background: #f5f9fd; }
h4 { margin: 0 0 9px; color: var(--aima-text); font-size: 13px; line-height: 18px; }
.analysis-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 9px !important; }
.analysis-summary span { padding: 3px 8px; border-radius: 4px; color: #cc2f58; background: var(--aima-primary-soft); font-size: 11px; }
.label-grid { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 9px; }
.label-grid span { padding: 3px 8px; border-radius: 4px; color: #396b9e; background: #e8f3ff; font-size: 11px; }
.label-grid em,
.empty { color: var(--aima-text-disabled); font-size: 11px; font-style: normal; }
.drawer-body section > small { color: var(--aima-text-disabled); font-size: 10px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.section-heading h4 { margin-bottom: 2px; }
.section-heading small { color: var(--aima-text-disabled); font-size: 9px; }
.section-heading > span { padding: 3px 7px; border-radius: 4px; color: var(--aima-primary); background: var(--aima-primary-soft); font-size: 9px; }
.manual-review { display: grid; gap: 10px; }
.evidence-list { display: grid; gap: 6px; }
.evidence-list article { display: grid; gap: 3px; padding: 7px 9px; border-radius: 5px; background: #f7f8fa; }
.evidence-list strong { color: var(--aima-text); font-size: 10px; }
.evidence-list span { color: var(--aima-text-muted); font-size: 9px; }
.unlock-confirm { display: flex; align-items: flex-start; gap: 6px; color: var(--aima-danger); font-size: 10px; line-height: 15px; }
.unlock-confirm input { margin: 1px 0 0; accent-color: var(--aima-primary); }
.review-actions { display: flex; justify-content: flex-end; gap: 8px; }
.review-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.review-grid label { display: grid; gap: 5px; color: var(--aima-text-muted); font-size: 10px; }
.review-grid select,
.label-editor select { height: 35px; padding: 0 9px; border: 1px solid var(--aima-border-strong); border-radius: 5px; color: var(--aima-text-secondary); background: var(--aima-surface); font-size: 11px; }
.label-editor { display: grid; grid-template-columns: 1fr 1fr auto; gap: 7px; }
.manual-labels { display: flex; flex-wrap: wrap; gap: 6px; }
.manual-labels button { padding: 3px 7px; border: 0; border-radius: 4px; color: #396b9e; background: #e8f3ff; cursor: pointer; font-size: 9px; }
.review-warning { padding: 8px 10px; border-radius: 5px; color: #8a641d !important; background: #fff9ec; }
dl { display: grid; grid-template-columns: 1fr 1fr; gap: 7px 8px; margin: 0; }
dl div { display: flex; min-height: 28px; align-items: flex-start; justify-content: space-between; gap: 10px; }
dt { color: var(--aima-text-disabled); font-size: 10px; }
dd { overflow-wrap: anywhere; margin: 0; color: var(--aima-text); font-size: 10px; font-weight: 500; text-align: right; }
.metric-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.metric-grid span { display: grid; min-height: 62px; place-items: center; align-content: center; gap: 3px; border-radius: 6px; color: var(--aima-text-disabled); background: #f2f4f7; font-size: 9px; text-align: center; }
.metric-grid b { color: var(--aima-text); font-size: 13px; }
.media-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.media-grid a { display: grid; min-height: 78px; place-items: center; overflow: hidden; border-radius: 7px; color: var(--aima-text-muted); background: #f2f4f7; font-size: 11px; text-decoration: none; }
.media-grid img { width: 100%; height: 120px; object-fit: cover; }
.coverage { margin-bottom: 8px !important; }
.comments article { padding: 9px 0; border-top: 1px solid #eef0f4; }
.comments strong { font-size: 11px; }
.comments time { float: right; color: var(--aima-text-disabled); font-size: 9px; }
.comments p { margin-top: 5px !important; font-size: 11px !important; }
.drawer-state { display: grid; flex: 1; place-items: center; color: var(--aima-text-muted); }
</style>
