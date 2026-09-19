<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type {
  AnalysisManualLabelRequest,
  ContentAnalysisManualReviewRequest,
  ContentAnalysisTaxonomyResponse,
  ContentCommentResponse,
  ContentDetailResponse,
} from '../../../../../generated/api/client'
import VehicleMultiSelect from '../../../../../shared/VehicleMultiSelect.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import { relevanceReviewActionLabel, relevanceReviewDecision, type RelevanceReviewDecision } from '../../../relevanceReview'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import type { CommentReplyState } from '../../../store'
import ContentCommentSection from './ContentCommentSection.vue'
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
  commentRoots?: ContentCommentResponse[]
  commentReplies?: Record<string, ContentCommentResponse[]>
  commentReplyStates?: Record<string, CommentReplyState>
  commentsLoading?: boolean
  commentsLoadingNext?: boolean
  commentsError?: string | null
  commentsHasMore?: boolean
  commentsTotalCount?: number
  commentsIngestedTotalCount?: number
}>(), {
  taxonomy: null,
  saving: false,
  error: null,
  saveError: null,
  commentRoots: () => [],
  commentReplies: () => ({}),
  commentReplyStates: () => ({}),
  commentsLoading: false,
  commentsLoadingNext: false,
  commentsError: null,
  commentsHasMore: false,
  commentsTotalCount: 0,
  commentsIngestedTotalCount: 0,
})
const emit = defineEmits<{
  'update:modelValue': [open: boolean]
  'review-vehicles': [vehicleModelIds: string[], unlockExisting: boolean]
  'review-analysis': [request: Omit<ContentAnalysisManualReviewRequest, 'content_version'>]
  retry: []
  'retry-comments': []
  'load-more-comments': []
  'load-comment-replies': [rootCommentId: string, reset: boolean]
  review: [contentId: string, decision: RelevanceReviewDecision]
}>()

const editingVehicles = ref(false)
const editingAnalysis = ref(false)
const mediaGrid = ref<HTMLElement | null>(null)
const activeMediaIndex = ref(0)
const mediaNavigationTarget = ref<number | null>(null)
const relevanceDecision = computed(() => props.item ? relevanceReviewDecision(props.item) : null)
const mediaItems = computed(() => props.item?.media ?? [])
const hasMediaNavigation = computed(() =>
  props.item?.platform === 'xiaohongshu'
  && mediaItems.value.length > 1
  && mediaItems.value.some((media) => media.preview_url?.startsWith('/api/v1/contents/')),
)

type DetailSection = 'content' | 'analysis' | 'manual' | 'comments'
const contentSection = ref<HTMLElement | null>(null)
const analysisSection = ref<HTMLElement | null>(null)
const manualSection = ref<HTMLElement | null>(null)
const commentsSection = ref<HTMLElement | null>(null)

const detailNavigation: ReadonlyArray<{ key: DetailSection; label: string }> = [
  { key: 'content', label: '内容' },
  { key: 'analysis', label: 'AI 信息' },
  { key: 'manual', label: '人工确认' },
  { key: 'comments', label: '评论' },
]

/** 按正式 Figma 的四段导航滚动到详情抽屉内对应业务区块。 */
function scrollToDetailSection(section: DetailSection): void {
  const targets: Record<DetailSection, HTMLElement | null> = {
    content: contentSection.value,
    analysis: analysisSection.value,
    manual: manualSection.value,
    comments: commentsSection.value,
  }
  targets[section]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(() => props.item?.id, async () => {
  editingVehicles.value = false
  editingAnalysis.value = false
  activeMediaIndex.value = 0
  mediaNavigationTarget.value = null
  await nextTick()
  if (mediaGrid.value) mediaGrid.value.scrollLeft = 0
})

const vehicleModelIds = ref<string[]>([])
const voiceType = ref('')
const sentiment = ref('')
const labels = ref<AnalysisManualLabelRequest[]>([])
const labelPrimary = ref('')
const labelSecondary = ref('')
const confirmUnlockVehicles = ref(false)
const confirmUnlockAnalysis = ref(false)
const unlockTarget = ref<'vehicles' | 'analysis' | null>(null)
const unlockDialogOpen = computed({
  get: () => unlockTarget.value !== null,
  set: (open: boolean) => { if (!open) unlockTarget.value = null },
})
const unlockDialogMessage = computed(() => unlockTarget.value === 'vehicles'
  ? '确定解除当前车型人工结论吗？解除后，自动识别结果会重新生效。'
  : '确定解除已人工确认的 AI 分析结果吗？解除后，当前 AI 结果会重新生效。')

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
  unlockTarget.value = null
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
  unlockTarget.value = 'vehicles'
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
  unlockTarget.value = 'analysis'
}

function confirmUnlockReview(): void {
  if (unlockTarget.value === 'vehicles') emit('review-vehicles', [], true)
  else if (unlockTarget.value === 'analysis') {
    emit('review-analysis', { unlock_dimensions: [...lockedDimensions.value] })
  }
  unlockTarget.value = null
}

/** 将画廊移动到指定图片，并立即更新按钮与序号状态。 */
function showMedia(index: number): void {
  const grid = mediaGrid.value
  if (!grid || !hasMediaNavigation.value) return
  const targetIndex = Math.min(Math.max(index, 0), mediaItems.value.length - 1)
  const target = grid.children.item(targetIndex)
  if (!(target instanceof HTMLElement)) return
  const gridRect = grid.getBoundingClientRect()
  const targetRect = target.getBoundingClientRect()
  const targetLeft = grid.scrollLeft + targetRect.left - gridRect.left
  mediaNavigationTarget.value = targetIndex
  activeMediaIndex.value = targetIndex
  grid.scrollTo({ left: targetLeft, behavior: 'auto' })
  window.requestAnimationFrame(() => {
    if (mediaGrid.value !== grid || mediaNavigationTarget.value !== targetIndex) return
    mediaNavigationTarget.value = null
    syncMediaIndex()
  })
}

/** 根据原生触控或触控板滚动位置同步当前图片序号。 */
function syncMediaIndex(): void {
  const grid = mediaGrid.value
  if (!grid || !hasMediaNavigation.value) return
  const gridRect = grid.getBoundingClientRect()

  if (mediaNavigationTarget.value !== null) {
    const target = grid.children.item(mediaNavigationTarget.value)
    if (target instanceof HTMLElement) {
      const targetLeft = grid.scrollLeft + target.getBoundingClientRect().left - gridRect.left
      activeMediaIndex.value = mediaNavigationTarget.value
      if (Math.abs(grid.scrollLeft - targetLeft) <= 2) mediaNavigationTarget.value = null
      return
    }
    mediaNavigationTarget.value = null
  }

  let nearestIndex = 0
  let nearestDistance = Number.POSITIVE_INFINITY
  Array.from(grid.children).forEach((child, index) => {
    if (!(child instanceof HTMLElement)) return
    const distance = Math.abs(child.getBoundingClientRect().left - gridRect.left)
    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestIndex = index
    }
  })
  activeMediaIndex.value = nearestIndex
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
  if (normalized.includes('tikhub')) return '平台采集'
  if (normalized.includes('manual')) return '人工维护'
  return '平台采集'
}

/** 将第三方可用状态映射为业务状态，原始 code 不进入普通用户界面。 */
function availabilityLabel(status: string): string {
  if (status === 'available') return '当前可访问'
  if (status === 'unavailable_confirmed') return '已确认不可访问'
  if (status === 'unavailable_suspected') return '可能不可访问'
  return '状态待确认'
}

/** 将车型证据来源归一为用户语义；内部 source/catalog version 继续留在审计事实源。 */
function vehicleEvidenceLabel(source: string): string {
  const normalized = source.toLowerCase()
  if (normalized.includes('manual')) return '人工确认'
  if (normalized.includes('keyword') || normalized.includes('alias')) return '词包 / 别名识别'
  return '系统识别'
}

function brandRoleLabel(role: 'owned' | 'competitor' | 'other'): string {
  return role === 'owned' ? '自有品牌' : role === 'competitor' ? '竞品品牌' : '其他品牌'
}

function competitionScopeLabel(scope?: ContentDetailResponse['competition_scope']): string {
  return scope ? ({ owned_only: '仅自有品牌', competitor_only: '仅竞品品牌', mixed: '自有与竞品混合', other_only: '仅其他品牌', none_detected: '未识别品牌' })[scope] : '未识别品牌'
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
      <strong>详情加载失败</strong><p>暂时无法加载这条内容的完整详情，请稍后重试。</p><AimaButton @click="emit('retry')">
        重新加载
      </AimaButton>
    </div>
    <div
      v-if="saveError"
      class="drawer-save-error"
      role="alert"
    >
      操作未完成，当前输入已保留，请稍后重试。
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
      <nav
        class="detail-section-nav"
        aria-label="详情快捷导航"
      >
        <button
          v-for="entry in detailNavigation"
          :key="entry.key"
          type="button"
          @click="scrollToDetailSection(entry.key)"
        >
          {{ entry.label }}
        </button>
      </nav>

      <section
        ref="contentSection"
        class="hero detail-anchor"
      >
        <div class="badges">
          <span class="platform">{{ platformLabel(item.platform) }}</span>
          <span class="analysis">{{ item.analysis.status === 'completed' ? item.analysis.sentiment || '已分析' : item.analysis.status === 'stale' ? '需重新分析' : '未分析' }}</span>
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
        <div class="media-carousel">
          <div
            ref="mediaGrid"
            class="media-grid"
            :class="{ 'media-grid--carousel': hasMediaNavigation }"
            @scroll.passive="syncMediaIndex"
          >
            <a
              v-for="media in item.media ?? []"
              :key="`${media.position}:${media.url}`"
              :href="item.platform === 'xiaohongshu'
                ? (media.preview_url || media.url || undefined)
                : (media.url || media.preview_url || undefined)"
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
          <template v-if="hasMediaNavigation">
            <button
              class="media-navigation media-navigation--previous"
              type="button"
              aria-label="上一张图片"
              :disabled="activeMediaIndex === 0"
              @click="showMedia(activeMediaIndex - 1)"
            >
              <AimaIcon
                name="chevron-left"
                :size="20"
              />
            </button>
            <span
              class="media-position"
              aria-live="polite"
              aria-atomic="true"
            >{{ activeMediaIndex + 1 }} / {{ mediaItems.length }}</span>
            <button
              class="media-navigation media-navigation--next"
              type="button"
              aria-label="下一张图片"
              :disabled="activeMediaIndex === mediaItems.length - 1"
              @click="showMedia(activeMediaIndex + 1)"
            >
              <AimaIcon
                name="chevron-right"
                :size="20"
              />
            </button>
          </template>
        </div>
      </section>
      <section
        ref="analysisSection"
        class="content-info detail-anchor"
      >
        <h4>内容与 AI 信息</h4>
        <dl class="info-grid">
          <div><dt>平台</dt><dd>{{ platformLabel(item.platform) }}</dd></div>
          <div><dt>作者</dt><dd>{{ item.author_display_name || '未知作者' }}</dd></div>
          <div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div>
          <div><dt>品牌</dt><dd>{{ (item.brands ?? []).map(brand => `${brand.display_name}（${brandRoleLabel(brand.role)}）`).join('、') || '未识别' }}</dd></div>
          <div><dt>车型</dt><dd>{{ (item.vehicles ?? []).map(vehicle => vehicle.display_name).join('、') || '未识别' }}</dd></div>
          <div><dt>竞争范围</dt><dd>{{ competitionScopeLabel(item.competition_scope) }}</dd></div>
          <div><dt>AI 分析</dt><dd>{{ item.analysis.relevance === 'relevant' ? '相关' : item.analysis.relevance === 'irrelevant' ? '不相关' : '未判定' }} · {{ item.analysis.sentiment || '未判定' }} · {{ item.analysis.voice_type || '未判定' }}</dd></div>
          <div><dt>标签</dt><dd>{{ (item.analysis.labels ?? []).map(labelPairText).join('、') || '暂无 AI 标签' }}</dd></div>
        </dl>
      </section>
      <section class="classification-evidence">
        <h4>品牌与车型识别</h4>
        <div class="evidence-columns">
          <div>
            <strong>品牌识别证据</strong><article
              v-for="brand in item.brands ?? []"
              :key="brand.id"
            >
              <b>{{ brand.display_name }} · {{ brandRoleLabel(brand.role) }}</b><span
                v-for="(evidence, index) in brand.evidences"
                :key="`${brand.id}:${index}`"
              >{{ vehicleEvidenceLabel(evidence.source) }}<template v-if="evidence.matched_text"> · 命中“{{ evidence.matched_text }}”</template></span>
            </article><small v-if="!(item.brands ?? []).length">暂无品牌证据</small>
          </div>
          <div>
            <strong>车型识别证据</strong><article
              v-for="vehicle in item.vehicles ?? []"
              :key="vehicle.vehicle_model_id"
            >
              <b>{{ vehicle.display_name }}<template v-if="vehicle.brand"> · 所属 {{ vehicle.brand.display_name }}</template></b><span
                v-for="(evidence, index) in vehicle.evidences"
                :key="`${vehicle.vehicle_model_id}:${index}`"
              >{{ vehicleEvidenceLabel(evidence.source) }}<template v-if="evidence.matched_text"> · 命中“{{ evidence.matched_text }}”</template></span>
            </article><small v-if="!item.vehicles?.length">暂无车型证据</small>
          </div>
        </div>
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
      <section
        ref="manualSection"
        class="manual-summary detail-anchor"
      >
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
          <span v-if="hasVehicleLock">已有人工结论</span>
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
        >我确认替换现有人工车型结论</label>
        <div class="review-actions">
          <AimaButton
            v-if="hasVehicleLock"
            size="small"
            @click="unlockVehicleReview"
          >
            解除人工结论
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
          <div><h4>发声类型、情感与标签人工纠正</h4><small>合法选项来自当前生效的 AI 分析规则。</small></div>
          <span v-if="lockedDimensions.length">已人工确认：{{ lockedDimensions.join('、') }}</span>
        </header>
        <p
          v-if="item.analysis.status !== 'completed'"
          class="review-warning"
        >
          尚无可纠正的当前 AI 结果，请先完成 AI 分析。
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
          >我确认替换已人工确认的分析结果</label>
          <div class="review-actions">
            <AimaButton
              v-if="lockedDimensions.length"
              size="small"
              @click="unlockAnalysisReview"
            >
              解除人工分析结论
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

      <div
        ref="commentsSection"
        class="detail-anchor comments-anchor"
      >
        <ContentCommentSection
          :roots="commentRoots"
          :replies="commentReplies"
          :reply-states="commentReplyStates"
          :loading="commentsLoading"
          :loading-next="commentsLoadingNext"
          :error="commentsError"
          :has-more="commentsHasMore"
          :root-total-count="commentsTotalCount"
          :ingested-total-count="commentsIngestedTotalCount"
          :provider-total-count="item.comment_coverage?.reported_total ?? item.metrics.comment_count"
          :coverage="item.comment_coverage?.coverage"
          @retry="emit('retry-comments')"
          @load-more-roots="emit('load-more-comments')"
          @load-replies="(rootCommentId, reset) => emit('load-comment-replies', rootCommentId, reset)"
        />
      </div>

      <details class="additional-details">
        <summary>更多信息</summary>
        <section>
          <h4>内容可用状态</h4><p>{{ contentTypeLabel(item.content_type) }} · {{ sourceLabel(item.source.provider_name) }}</p>
          <p v-if="item.availability">
            {{ availabilityLabel(item.availability.status) }} · 更新于 {{ formatDateTime(item.availability.observed_at) }}
          </p>
          <p v-else>
            状态待确认 · 暂无明确的平台可用性证据。
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

  <AimaDialog
    v-model="unlockDialogOpen"
    label="解除人工结论"
    width="480px"
    class="voice-unlock-modal"
  >
    <template #header>
      <header class="unlock-dialog-header">
        <div>
          <h2>解除人工结论</h2>
          <small>此操作会恢复当前自动识别 / AI 分析结果。</small>
        </div>
        <button
          class="close-button"
          type="button"
          aria-label="关闭"
          @click="unlockDialogOpen = false"
        >
          <AimaIcon
            name="close"
            :size="20"
          />
        </button>
      </header>
    </template>
    <div class="unlock-dialog-body">
      <strong>{{ unlockDialogMessage }}</strong>
      <p>原始分析记录仍会保留。</p>
    </div>
    <template #footer>
      <footer class="unlock-dialog-footer">
        <AimaButton @click="unlockDialogOpen = false">
          取消
        </AimaButton>
        <AimaButton
          variant="primary"
          @click="confirmUnlockReview"
        >
          确认解除
        </AimaButton>
      </footer>
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
.evidence-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.evidence-columns > div { display: grid; align-content: start; gap: 6px; padding: 10px; border: 1px solid var(--aima-border); border-radius: 7px; }.evidence-columns strong { color: var(--aima-text); font-size: 12px; }.evidence-columns article { display: grid; gap: 3px; padding: 7px; border-radius: 5px; background: var(--aima-color-bg-hover); }.evidence-columns b { color: var(--aima-text); font-size: 11px; }.evidence-columns span,.evidence-columns small { color: var(--aima-text-muted); font-size: 10px; }
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
.drawer-body { gap: 20px; padding: 0 24px 24px; overflow: visible; }
.detail-section-nav {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid var(--aima-border);
  background: var(--aima-surface);
}
.detail-section-nav button {
  height: 32px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  color: var(--aima-text-muted);
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  line-height: 18px;
}
.detail-section-nav button:hover,
.detail-section-nav button:focus-visible {
  color: var(--aima-primary);
  background: var(--aima-primary-soft);
  outline: none;
}
.detail-anchor { scroll-margin-top: 52px; }
.comments-anchor { min-width: 0; }
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
.media-carousel { position: relative; overflow: hidden; border-radius: 8px; }
.media-grid { grid-template-columns: 1fr; }
.media-grid img { height: 100px; }
.media-grid--carousel {
  grid-auto-flow: column;
  grid-auto-columns: 100%;
  grid-template-columns: none;
  overflow-x: auto;
  scroll-behavior: auto;
  scroll-snap-type: x mandatory;
  scrollbar-width: none;
}
.media-grid--carousel::-webkit-scrollbar { display: none; }
.media-grid--carousel a { scroll-snap-align: start; }
.media-grid--carousel img { height: 180px; }
.media-navigation {
  position: absolute;
  top: 50%;
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  transform: translateY(-50%);
  border: 1px solid rgb(255 255 255 / 70%);
  border-radius: 50%;
  color: var(--aima-text);
  background: rgb(255 255 255 / 88%);
  box-shadow: 0 2px 8px rgb(23 35 61 / 14%);
  cursor: pointer;
}
.media-navigation--previous { left: 8px; }
.media-navigation--next { right: 8px; }
.media-navigation:disabled { cursor: default; opacity: .38; }
.media-position {
  position: absolute;
  right: 10px;
  bottom: 8px;
  padding: 3px 8px;
  border-radius: 999px;
  color: white;
  background: rgb(17 22 37 / 65%);
  font-size: 10px;
}
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
.unlock-dialog-header { min-height: 64px; padding: 0 20px; }
.unlock-dialog-header h2 { margin-bottom: 2px; font-size: 16px; line-height: 22px; }
.unlock-dialog-header small { font-size: 11px; }
.unlock-dialog-body { display: grid; gap: 10px; padding: 20px; }
.unlock-dialog-body strong { color: var(--aima-text); font-size: 13px; line-height: 20px; }
.unlock-dialog-body p { margin: 0; color: var(--aima-text-muted); font-size: 11px; line-height: 18px; }
.unlock-dialog-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px 20px; }
.drawer-state { min-height: 180px; align-content: center; gap: 12px; padding: 24px; }
.drawer-save-error { padding: 12px 24px; color: var(--aima-danger); font-size: 12px; }
</style>
<style>
.content-detail-dialog { height: 100dvh; max-height: 100dvh; max-width: 100vw; margin: 0 0 0 auto; border-radius: 12px 0 0 12px; }
.content-detail-dialog > .aima-dialog-body { flex: 1; }
</style>
