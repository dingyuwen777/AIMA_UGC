<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  AnalysisManualLabelRequest,
  ContentAnalysisManualReviewRequest,
  ContentAnalysisTaxonomyResponse,
  ContentDetailResponse,
} from '../../../../../generated/api/client'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import { relevanceReviewActionLabel, relevanceReviewDecision, type RelevanceReviewDecision } from '../../../relevanceReview'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import {
  contentSummary,
  contentTypeLabel,
  formatDateTime,
  formatNumber,
  labelPairText,
  platformLabel,
} from '../../../format'

const props = withDefaults(defineProps<{
  modelValue: boolean
  item: ContentDetailResponse | null
  loading: boolean
  taxonomy?: ContentAnalysisTaxonomyResponse | null
  saving?: boolean
  error?: string | null
  saveError?: string | null
}>(), { taxonomy: null, saving: false, error: null, saveError: null })
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  'review-vehicles': [vehicleModelIds: string[], unlockExisting: boolean]
  'review-analysis': [request: Omit<ContentAnalysisManualReviewRequest, 'content_version'>]
  retry: []
  review: [contentId: string, decision: RelevanceReviewDecision]
}>()

const editingVehicles = ref(false)
const editingAnalysis = ref(false)
const relevanceDecision = computed(() => props.item ? relevanceReviewDecision(props.item) : null)

watch(() => props.item?.id, () => { editingVehicles.value = false; editingAnalysis.value = false })

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

/** 将内部 Provider 名称归一为用户可理解的来源类别。 */
function sourceLabel(providerName: string): string {
  const normalized = providerName.toLowerCase()
  if (normalized.includes('import') || normalized.includes('excel')) return '数据导入'
  if (normalized.includes('tikhub')) return 'TikHub 采集'
  if (normalized.includes('manual')) return '人工维护'
  return '平台采集'
}

/** 将第三方可用状态映射为业务状态，原始 code 仅在技术详情保留。 */
function availabilityLabel(status: string): string {
  if (status === 'available') return '当前可访问'
  if (status === 'unavailable_confirmed') return '已确认不可访问'
  if (status === 'unavailable_suspected') return '可能不可访问'
  return '状态待确认'
}

/** 将车型证据来源归一为用户语义；内部 source/catalog version 下沉技术详情。 */
function vehicleEvidenceLabel(source: string): string {
  const normalized = source.toLowerCase()
  if (normalized.includes('manual')) return '人工确认'
  if (normalized.includes('keyword') || normalized.includes('alias')) return '词包 / 别名识别'
  return '系统识别'
}

/** 将评论覆盖枚举转换为用户可读状态。 */
function commentCoverageLabel(value: string): string {
  if (value === 'complete') return '完整'
  if (value === 'partial') return '部分'
  return '待确认'
}
</script>

<template>
  <AimaDialog
    :model-value="modelValue"
    label="内容详情"
    width="610px"
    class="content-detail-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header>
        <div>
          <h2>内容详情</h2>
          <small v-if="item">{{ platformLabel(item.platform) }} · {{ item.author_display_name || '未知作者' }} · {{ formatDateTime(item.published_at) }}</small>
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
    </template>
    <div
      v-if="error"
      class="drawer-state"
      role="alert"
    >
      <strong>详情加载失败</strong><p>{{ error }}</p><AimaButton @click="emit('retry')">
        重新加载
      </AimaButton>
    </div>
    <div
      v-if="saveError"
      class="drawer-save-error"
      role="alert"
    >
      {{ saveError }}
    </div>
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
      </section>

      <section
        v-if="item.supplement_status && item.supplement_status.status !== 'succeeded'"
        class="supplement-status"
        :class="`supplement-status--${item.supplement_status.status}`"
      >
        <h4>{{ supplementTitle(item.supplement_status.status) }}</h4>
        <p>{{ supplementMessage(item.supplement_status.status) }}</p>
      </section>

      <section v-if="(item.media ?? []).length > 0">
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
      <section class="content-info">
        <h4>内容与 AI 信息</h4>
        <dl class="info-grid">
          <div><dt>平台</dt><dd>{{ platformLabel(item.platform) }}</dd></div>
          <div><dt>作者</dt><dd>{{ item.author_display_name || '未知作者' }}</dd></div>
          <div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div>
          <div><dt>车型</dt><dd>{{ (item.vehicles ?? []).map(vehicle => vehicle.display_name).join('、') || '未识别' }}</dd></div>
          <div><dt>AI 分析</dt><dd>{{ item.analysis.relevance === 'relevant' ? '相关' : item.analysis.relevance === 'irrelevant' ? '不相关' : '未判定' }} · {{ item.analysis.sentiment || '未判定' }} · {{ item.analysis.voice_type || '未判定' }}</dd></div>
          <div><dt>标签</dt><dd>{{ (item.analysis.labels ?? []).map(labelPairText).join('、') || '暂无 AI 标签' }}</dd></div>
        </dl>
      </section>
      <section class="metrics-section">
        <div class="metric-grid">
          <span>点赞<b>{{ formatNumber(item.metrics.like_count) }}</b></span>
          <span>评论<b>{{ formatNumber(item.metrics.comment_count) }}</b></span>
          <span>分享<b>{{ formatNumber(item.metrics.share_count) }}</b></span>
          <span>收藏<b>{{ formatNumber(item.metrics.favorite_count) }}</b></span>
          <span v-if="item.metrics.play_count != null">播放<b>{{ formatNumber(item.metrics.play_count) }}</b></span>
          <span v-if="item.metrics.view_count != null">浏览<b>{{ formatNumber(item.metrics.view_count) }}</b></span>
        </div>
      </section>
      <section class="manual-summary">
        <h4>人工确认</h4>
        <div>
          <strong>相关性</strong><span>{{ item.effective_relevance === 'relevant' ? '相关' : item.effective_relevance === 'irrelevant' ? '不相关' : '未判定' }} · {{ item.relevance_source === 'manual_review' ? '已人工确认' : '人工未覆盖' }}</span><AimaButton
            v-if="relevanceDecision"
            size="small"
            :disabled="saving"
            @click="emit('review', item.id, relevanceDecision)"
          >
            {{ relevanceReviewActionLabel(relevanceDecision) }}
          </AimaButton>
        </div>
        <div>
          <strong>车型</strong><span>{{ (item.vehicles ?? []).map(vehicle => vehicle.display_name).join('、') || '未识别' }}</span><AimaButton
            size="small"
            :aria-expanded="editingVehicles"
            @click="editingVehicles = !editingVehicles"
          >
            {{ editingVehicles ? '收起修改' : '修改车型' }}
          </AimaButton>
        </div>
        <div>
          <strong>AI 结果</strong><span>{{ item.analysis.voice_type || '未判定' }} · {{ item.analysis.sentiment || '未判定' }}</span><AimaButton
            size="small"
            :aria-expanded="editingAnalysis"
            @click="editingAnalysis = !editingAnalysis"
          >
            {{ editingAnalysis ? '收起纠正' : '人工纠正' }}
          </AimaButton>
        </div>
        <small>人工确认结果优先生效；撤销后恢复当前 AI / 自动识别结果。</small>
      </section>


      <section
        v-if="editingVehicles"
        class="manual-review"
      >
        <header class="section-heading">
          <div><h4>车型人工确认</h4><small>0..N 个车型；自动别名证据与人工结论分开保留。</small></div>
          <span v-if="hasVehicleLock">已人工锁定</span>
        </header>
        <VehicleMultiSelect
          v-model="vehicleModelIds"
          label="当前车型"
          compact
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
              {{ vehicleEvidenceLabel(evidence.source) }}<template v-if="evidence.matched_text"> · 命中“{{ evidence.matched_text }}”</template><template v-if="evidence.is_manual_locked"> · 已人工确认</template>
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

      <section
        v-if="editingAnalysis"
        class="manual-review"
      >
        <header class="section-heading">
          <div><h4>发声类型、情感与标签人工纠正</h4><small>合法选项来自当前生效的 AI 分析原则。</small></div>
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

      <details class="additional-details">
        <summary>更多信息与评论</summary>
        <section>
          <h4>内容可用状态</h4><p>{{ contentTypeLabel(item.content_type) }} · {{ sourceLabel(item.source.provider_name) }}</p>
          <p v-if="item.availability">
            {{ availabilityLabel(item.availability.status) }} · 更新于 {{ formatDateTime(item.availability.observed_at) }}
          </p>
          <p v-else>
            状态待确认 · 暂无明确的平台可用性证据。
          </p>
        </section>





        <section class="technical-section">
          <details class="technical-details">
            <summary>技术详情</summary>
            <dl>
              <div><dt>Content ID</dt><dd>{{ item.id }}</dd></div>
              <div><dt>外部内容 ID</dt><dd>{{ item.external_content_id }}</dd></div>
              <div><dt>当前来源 Provider</dt><dd>{{ item.source.provider_name }}</dd></div>
              <div><dt>Provider Attempt</dt><dd>{{ item.source.provider_attempt_id || '—' }}</dd></div>
              <div><dt>Raw Artifact</dt><dd>{{ item.source.raw_artifact_id || '—' }}</dd></div>
              <div><dt>Import Batch</dt><dd>{{ item.source.import_batch_id || '—' }}</dd></div>
              <div><dt>Collection Run</dt><dd>{{ item.source.collection_run_id || '—' }}</dd></div>
              <div><dt>AI 模型</dt><dd>{{ item.analysis.model_provider }} / {{ item.analysis.model }}</dd></div>
              <div v-if="item.availability">
                <dt>可用状态原始证据</dt><dd>{{ item.availability.status }} · {{ item.availability.reason_code }} · {{ item.availability.evidence_kind }}</dd>
              </div>
            </dl>
            <div
              v-if="(item.source_records ?? []).length"
              class="technical-list"
            >
              <strong>来源追溯</strong>
              <span
                v-for="(source, index) in item.source_records ?? []"
                :key="`${source.provider_attempt_id ?? source.raw_artifact_id ?? index}`"
              >
                {{ source.provider_name }}<template v-if="source.import_batch_id"> · Import {{ source.import_batch_id }}</template><template v-if="source.collection_run_id"> · Run {{ source.collection_run_id }}</template><template v-if="source.provider_attempt_id"> · Attempt {{ source.provider_attempt_id }}</template><template v-if="source.raw_artifact_id"> · Artifact {{ source.raw_artifact_id }}</template>
              </span>
            </div>
            <div
              v-if="(item.vehicles ?? []).some((vehicle) => vehicle.evidences.length)"
              class="technical-list"
            >
              <strong>车型证据追溯</strong>
              <template
                v-for="vehicle in item.vehicles ?? []"
                :key="vehicle.vehicle_model_id"
              >
                <span
                  v-for="(evidence, index) in vehicle.evidences"
                  :key="`${vehicle.vehicle_model_id}:${index}`"
                >{{ vehicle.display_name }} · {{ evidence.source }} · catalog v{{ evidence.catalog_version }}<template v-if="evidence.source_field"> · {{ evidence.source_field }}</template></span>
              </template>
            </div>
          </details>
        </section>



        <section>
          <h4>评论与覆盖</h4>
          <p
            v-if="item.comment_coverage"
            class="coverage"
          >
            已采集 {{ formatNumber(item.comment_coverage.collected_count) }} / {{ formatNumber(item.comment_coverage.reported_total) }}，覆盖状态：{{ commentCoverageLabel(item.comment_coverage.coverage) }}
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
      </details>
    </div>
    <template #footer>
      <a
        v-if="item?.content_url"
        class="original-link"
        :href="item.content_url"
        target="_blank"
        rel="noopener noreferrer"
      >查看原始链接 ↗</a>
    </template>
  </AimaDialog>
</template>

<style scoped>
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
.technical-section { padding: 0 !important; border: 0 !important; background: transparent !important; }
.technical-details { padding: 10px 12px; border: 1px dashed var(--aima-border-strong); border-radius: 7px; color: var(--aima-text-muted); background: #fafbfc; font-size: 10px; }
.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-weight: 600; }
.technical-details dl { margin-top: 10px; }
.technical-list { display: grid; gap: 4px; margin-top: 10px; padding-top: 9px; border-top: 1px solid var(--aima-border); }
.technical-list strong { color: var(--aima-text-secondary); font-size: 10px; }
.technical-list span { overflow-wrap: anywhere; color: var(--aima-text-muted); font-size: 9px; line-height: 15px; }
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
.drawer-body { gap: 20px; padding: 0 24px 24px; overflow: visible; }
header { min-height: 80px; padding: 24px 24px 16px; border: 0; }
header h2 { margin: 0 0 4px; font-size: 16px; line-height: 22px; }
header small { font-size: 12px; }
.drawer-body > section { padding: 0; border: 0; }
.drawer-body > .hero { gap: 14px; padding: 0; }
.hero h3 { font-size: 16px; line-height: 24px; }
.hero p { color: var(--aima-text-muted); font-size: 13px; line-height: 22px; white-space: pre-wrap; overflow-wrap: anywhere; }
.info-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.info-grid div { display: grid; align-content: start; justify-content: stretch; gap: 2px; min-height: 58px; padding: 10px 12px; border-radius: 6px; background: #f7f9fb; }
.info-grid dt { font-size: 12px; }
.info-grid dd { font-size: 13px; line-height: 20px; text-align: left; }
.metric-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.metric-grid span { min-height: 64px; padding: 10px 12px; place-items: start; align-content: center; background: #f7f9fb; font-size: 12px; }
.media-grid { grid-template-columns: 1fr; }
.media-grid img { height: 100px; }
.drawer-body > .manual-summary { display: grid; gap: 6px; padding: 12px; border-radius: 6px; background: #f7f9fb; }
.manual-summary h4 { margin: 0; font-size: 16px; }
.manual-summary > div { display: flex; min-height: 32px; align-items: center; gap: 12px; border-radius: 4px; background: white; }
.manual-summary strong { width: 78px; flex: none; font-size: 12px; font-weight: 400; }
.manual-summary span { min-width: 0; flex: 1; color: var(--aima-text-muted); font-size: 12px; overflow-wrap: anywhere; }
.manual-summary :deep(.aima-button) { flex: none; height: 32px; }
.manual-summary small { font-size: 11px; }
.original-link { display: flex; height: 40px; align-items: center; justify-content: center; margin: 16px 24px 24px; border-radius: 6px; color: white; background: var(--aima-primary); text-decoration: none; font-size: 13px; }
.additional-details { display: grid; gap: 12px; color: var(--aima-text-muted); font-size: 12px; }
.additional-details > summary { cursor: pointer; }
.additional-details > section { margin-top: 16px; }
.drawer-state { min-height: 180px; align-content: center; gap: 12px; padding: 24px; }
.drawer-save-error { padding: 12px 24px; color: var(--aima-danger); font-size: 12px; }
</style>
<style>
.content-detail-dialog { height: 100dvh; max-height: 100dvh; max-width: 100vw; margin: 0 0 0 auto; border-radius: 12px 0 0 12px; }
.content-detail-dialog > .aima-dialog-body { flex: 1; }
</style>
