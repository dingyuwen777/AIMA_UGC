<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { BrandResponse, ReportPreflightResponse, ReportResponse, ReportSubmitRequest, VehicleModelResponse } from '../../../../../generated/api/client'
import { apiErrorMessage } from '../../../../../shared/api/http'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { cancelDatabaseReport, createDatabaseReport, fetchDatabaseReports, fetchVehicleBrandsForAdmin, fetchVehicles, preflightDatabaseReport, publishDatabaseReport, retryDatabaseReport } from '../../../api'

const emit = defineEmits<{ 'dirty-change': [dirty: boolean] }>()
const brands = ref<BrandResponse[]>([])
const vehicles = ref<VehicleModelResponse[]>([])
const brandId = ref('')
const vehicleIds = ref<string[]>([])
const startDate = ref('')
const endDate = ref('')
const preflight = ref<ReportPreflightResponse | null>(null)
const reports = ref<ReportResponse[]>([])
const loading = ref(false)
const pendingAction = ref<string | null>(null)
const error = ref('')
const pollError = ref('')
let poll: ReturnType<typeof setInterval> | undefined
let refreshing = false
let disposed = false
let formEpoch = 0
let mutationEpoch = 0

const filteredVehicles = computed(() => vehicles.value.filter((vehicle) => vehicle.brand_id === brandId.value && vehicle.status === 'active'))
const valid = computed(() => Boolean(brandId.value && startDate.value && endDate.value && startDate.value <= endDate.value))
const form = computed<ReportSubmitRequest>(() => ({ brand_id: brandId.value, vehicle_model_ids: vehicleIds.value, start_date: startDate.value, end_date: endDate.value }))
const active = (report: ReportResponse): boolean => [report.generation_job, report.publication_job].some((job) => job && ['queued', 'running'].includes(job.status))
const statusLabels: Record<ReportResponse['status'], string> = { queued: '排队中', generating: '生成中', generated: '可下载', published: '已发布', failed: '生成失败', cancelled: '已取消', expired: '已过期' }

watch(brandId, () => { vehicleIds.value = [] })
watch(form, () => {
  formEpoch += 1
  preflight.value = null
  emit('dirty-change', Boolean(brandId.value || startDate.value || endDate.value))
}, { deep: true })

/** 预检响应必须对应当前输入；修改范围后丢弃旧结果。 */
async function inspect(): Promise<void> {
  if (!valid.value || loading.value) return
  const epoch = formEpoch
  loading.value = true
  error.value = ''
  try {
    const result = await preflightDatabaseReport(form.value)
    if (!disposed && epoch === formEpoch) preflight.value = result
  } catch (cause) { error.value = apiErrorMessage(cause) }
  finally { loading.value = false }
}

/** 历史读取失败保留已显示的下载和任务，下一轮自动恢复。 */
async function refresh(): Promise<void> {
  if (refreshing || disposed) return
  refreshing = true
  const epoch = mutationEpoch
  try {
    const result = await fetchDatabaseReports()
    if (!Array.isArray(result.items)) throw new Error('报告状态响应不完整，请稍后重试。')
    if (!disposed && epoch === mutationEpoch) { reports.value = result.items; pollError.value = '' }
  } catch (cause) { if (!disposed) pollError.value = apiErrorMessage(cause) }
  finally { refreshing = false }
}

/** 生成只排队数据库报告；飞书发布由历史操作单独发起。 */
async function generate(): Promise<void> {
  if (!preflight.value?.ready || !valid.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const report = await createDatabaseReport(form.value)
    mutationEpoch += 1
    reports.value = [report, ...reports.value.filter((item) => item.id !== report.id)]
    emit('dirty-change', false)
    preflight.value = null
  } catch (cause) { error.value = apiErrorMessage(cause) }
  finally { loading.value = false }
}

/** 后端父事实锁负责跨页面幂等，本页面同时限制重复操作。 */
async function act(report: ReportResponse, action: 'publish' | 'retry' | 'cancel'): Promise<void> {
  if (pendingAction.value) return
  pendingAction.value = report.id
  error.value = ''
  try {
    const operation = action === 'publish' ? publishDatabaseReport : action === 'retry' ? retryDatabaseReport : cancelDatabaseReport
    const result = await operation(report.id)
    mutationEpoch += 1
    reports.value = reports.value.map((item) => item.id === result.id ? result : item)
  } catch (cause) { error.value = apiErrorMessage(cause) }
  finally { pendingAction.value = null }
}

/** 加载正式品牌车型目录，用单一有界轮询读取持久任务。 */
onMounted(async () => {
  try {
    const [brandList, vehicleList] = await Promise.all([fetchVehicleBrandsForAdmin(), fetchVehicles()])
    if (!disposed) { brands.value = brandList.items.filter((brand) => brand.status === 'active'); vehicles.value = vehicleList.items }
  } catch (cause) { error.value = apiErrorMessage(cause) }
  await refresh()
  if (!disposed) poll = setInterval(() => { if (reports.value.some(active) || pollError.value) void refresh() }, 3000)
})
onBeforeUnmount(() => { disposed = true; if (poll) clearInterval(poll) })
</script>

<template>
  <section
    class="report-panel"
    aria-label="数据库报告生成"
  >
    <div class="report-heading">
      <h2>报告生成</h2>
      <p>选择品牌、车型和监测周期，从数据库生成 Word 和 Excel。本期与相邻上期数据会一并冻结。</p>
    </div>
    <AimaFeedbackBanner
      v-if="error"
      tone="error"
    >
      {{ error }}
    </AimaFeedbackBanner>
    <div class="report-form">
      <label>品牌
        <select
          v-model="brandId"
          :disabled="loading"
          aria-label="报告品牌"
        >
          <option value="">请选择品牌</option>
          <option
            v-for="brand in brands"
            :key="brand.id"
            :value="brand.id"
          >{{ brand.display_name }}</option>
        </select>
      </label>
      <label>车型（可选，未选择表示全部车型）
        <select
          v-model="vehicleIds"
          multiple
          :disabled="!brandId || loading"
          aria-label="报告车型"
        >
          <option
            v-for="vehicle in filteredVehicles"
            :key="vehicle.id"
            :value="vehicle.id"
          >{{ vehicle.display_name }}</option>
        </select>
      </label>
      <label>开始日期<input
        v-model="startDate"
        type="date"
        :disabled="loading"
        aria-label="报告开始日期"
      ></label>
      <label>结束日期<input
        v-model="endDate"
        type="date"
        :min="startDate"
        :disabled="loading"
        aria-label="报告结束日期"
      ></label>
    </div>
    <div class="report-actions">
      <AimaButton
        :disabled="!valid || loading"
        @click="inspect"
      >
        {{ loading ? '处理中…' : '检查数据与模型' }}
      </AimaButton>
      <AimaButton
        variant="primary"
        :disabled="!valid || !preflight?.ready || loading"
        @click="generate"
      >
        生成报告
      </AimaButton>
    </div>
    <section
      v-if="preflight"
      class="preflight"
      aria-label="报告预检"
    >
      <p>本期 {{ preflight.content_count }} 条 · 上期 {{ preflight.previous_content_count }} 条 · 已分析 {{ preflight.analyzed_count }} 条 · 真实用户 {{ preflight.real_user_count }} 条 · 评论 {{ preflight.comment_count }} 条</p>
      <p>本次筛选与建议模型：{{ preflight.model || '未配置' }} · 当前规则：{{ preflight.prompt_version }}</p>
      <p>内容统计沿用已有分析结果；创建报告时冻结各条内容实际使用的历史规则与人工修订。</p>
      <p
        v-for="warning in preflight.warnings"
        :key="warning"
        class="warning"
      >
        {{ warning }}
      </p>
    </section>
    <div class="history-heading">
      <h3>历史报告</h3><AimaButton @click="refresh">
        刷新
      </AimaButton>
    </div>
    <AimaFeedbackBanner
      v-if="pollError"
      class="poll-status"
      tone="warning"
    >
      状态同步暂时失败，正在重试：{{ pollError }}
    </AimaFeedbackBanner>
    <p
      v-if="reports.length === 0"
      class="empty"
    >
      暂无报告。完成预检后可以创建第一份报告。
    </p>
    <article
      v-for="report in reports"
      :key="report.id"
      class="report-card"
      :aria-label="report.name"
    >
      <div class="report-card-heading">
        <strong>{{ report.name }}</strong><span>{{ statusLabels[report.status] }}</span>
      </div>
      <p>{{ report.content_count }} 条内容 · {{ report.model }} · {{ report.prompt_version }}</p>
      <details class="report-basis">
        <summary>查看生成依据</summary>
        <p>筛选与建议：{{ report.model }} · 模型配置修订 {{ report.provider_revision }} · 配置 ID {{ report.provider_config_id }}</p>
        <p>创建时规则：{{ report.prompt_version }} · 版本 ID {{ report.scheme_version_id }}</p>
        <p>规则摘要：{{ report.prompt_sha256 }}<br>标签摘要：{{ report.taxonomy_sha256 }}<br>筛选提示词摘要：{{ report.selection_prompt_sha256 }}</p>
        <p v-if="!report.analysis_bases?.length">
          此报告没有可用的内容分析结果，仅提供全量声量统计。
        </p>
        <p
          v-for="(basis, index) in report.analysis_bases"
          :key="index"
        >
          {{ basis.period === 'current' ? '本期' : '上期' }}已有分析：{{ basis.content_count }} 条 · {{ basis.model }} · {{ basis.prompt_version }} · 人工修订 {{ basis.manual_override_count }} 条<br>
          规则版本 {{ basis.scheme_version_id }} · 规则摘要 {{ basis.prompt_sha256 }} · 标签摘要 {{ basis.taxonomy_sha256 }}
        </p>
      </details>
      <TaskProgressBar
        v-if="['queued', 'generating'].includes(report.status)"
        label="报告生成"
        :value="report.generation_job.progress"
      />
      <p
        v-if="report.generation_job.status === 'queued' && report.generation_job.attempt > 0"
        class="warning"
      >
        模型或服务暂时不可用，已安排重试（{{ report.generation_job.attempt }}/{{ report.generation_job.max_attempts }}），下次执行：{{ report.generation_job.available_at }}
      </p>
      <p
        v-if="report.generation_job.error_code"
        class="warning"
      >
        生成提示：{{ report.generation_job.error_code }}
      </p>
      <p v-if="report.expires_at">
        文件保留至 {{ report.expires_at }}；过期后保留报告记录。
      </p>
      <p v-if="report.status === 'expired'">
        报告文件已过期，请创建新报告。
      </p>
      <div class="report-actions">
        <a
          v-for="file in (report.files ?? []).filter((item) => ['word_report', 'excel_report', 'chart_workbook', 'markdown_source'].includes(item.artifact_type))"
          :key="file.artifact_id"
          :href="file.download_url"
          download
        >{{ file.artifact_type === 'word_report' ? '下载 Word' : file.artifact_type === 'excel_report' ? '下载 Excel 数据' : file.artifact_type === 'chart_workbook' ? '下载可编辑图表' : '下载 Markdown' }}</a>
        <AimaButton
          v-if="['generated', 'published'].includes(report.status) && !active(report) && report.publication_job?.status !== 'succeeded'"
          :disabled="Boolean(pendingAction) || !report.publication_enabled"
          @click="act(report, 'publish')"
        >
          {{ report.publication_job ? '重试飞书发布' : '发布到飞书' }}
        </AimaButton>
        <AimaButton
          v-if="['failed', 'cancelled'].includes(report.status)"
          :disabled="Boolean(pendingAction)"
          @click="act(report, 'retry')"
        >
          重试生成
        </AimaButton>
        <AimaButton
          v-if="active(report)"
          :disabled="Boolean(pendingAction) || report.generation_job.cancel_requested || report.publication_job?.cancel_requested"
          @click="act(report, 'cancel')"
        >
          取消任务
        </AimaButton>
      </div>
      <section
        v-if="report.publication_job"
        aria-label="飞书发布状态"
      >
        <p>飞书发布：{{ report.publication_job.status === 'failed' ? '失败，报告文件仍可下载' : report.publication_job.status === 'succeeded' ? '已完成' : report.publication_job.status === 'cancelled' ? '已取消' : '正在处理' }}（{{ report.publication_job.attempt }}/{{ report.publication_job.max_attempts }}）</p>
        <TaskProgressBar
          v-if="['queued', 'running'].includes(report.publication_job.status)"
          label="飞书发布"
          :value="report.publication_job.progress"
        />
        <p
          v-if="report.publication_job.error_code"
          class="warning"
        >
          {{ report.publication_job.error_code }}<span v-if="report.publication_job.status === 'queued'"> · 下次重试：{{ report.publication_job.available_at }}</span>
        </p>
      </section>
      <p
        v-if="!report.publication_enabled"
        class="warning"
      >
        飞书当前为预演模式，真实发布已关闭；报告文件仍可下载。
      </p>
      <div class="report-actions">
        <a
          v-if="report.native_document_url"
          :href="report.native_document_url"
          target="_blank"
          rel="noopener noreferrer"
        >打开飞书报告</a>
        <a
          v-if="report.editable_chart_sheet_url"
          :href="report.editable_chart_sheet_url"
          target="_blank"
          rel="noopener noreferrer"
        >打开飞书图表</a>
        <a
          v-if="report.representative_table_url"
          :href="report.representative_table_url"
          target="_blank"
          rel="noopener noreferrer"
        >打开多维表</a>
      </div>
    </article>
  </section>
</template>

<style scoped>
.report-panel { position: relative; display: grid; gap: 20px; }
.poll-status { position: absolute; z-index: 3; top: 0; right: 0; max-width: min(560px, 100%); }
.report-heading h2, .history-heading h3 { margin: 0; }
.report-heading p, .report-card p { color: var(--text-secondary, #64748b); line-height: 1.6; }
.report-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
label { display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
select, input { border: 1px solid var(--border-color, #dbe2eb); border-radius: 8px; padding: 10px; color: inherit; background: var(--surface, #fff); font: inherit; }
.report-actions, .history-heading, .report-card-heading { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.history-heading, .report-card-heading { justify-content: space-between; }
.report-card, .preflight { padding: 20px; border: 1px solid var(--border-color, #dbe2eb); border-radius: 12px; background: var(--surface, #fff); }
.warning { color: #a16207 !important; }
.empty { padding: 28px; text-align: center; color: var(--text-secondary, #64748b); }
.report-basis { overflow-wrap: anywhere; color: var(--text-secondary, #64748b); }
a { color: var(--primary-color, #2563eb); font-size: 14px; }
@media (max-width: 700px) { .report-form { grid-template-columns: 1fr; } }
</style>
