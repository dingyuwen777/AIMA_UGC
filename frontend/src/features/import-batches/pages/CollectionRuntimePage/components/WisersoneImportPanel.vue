<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'

import type { WisersOneDownloadResponse } from '../../../../../generated/api/client'
import TaskProgressBar from '../../../../../shared/TaskProgressBar.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { formatDateTime } from '../../../format'
import { useImportBatchesStore } from '../../../store'

const emit = defineEmits<{ 'view-result': [campaignId: string] }>()
const store = useImportBatchesStore()
const labels: Record<WisersOneDownloadResponse['status'], string> = {
  queued: '等待下载', submitting: '正在提交网站导出', waiting: '网站正在生成 Excel',
  downloading: '正在保存 Excel', preflight: '正在预检数据', importing: '正在导入系统',
  succeeded: '导入完成', partial_failed: '部分导入失败', failed: '任务失败',
  cancelling: '正在取消并等待导入停止', cancelled: '已取消', attention: '需要核对网站提交结果',
}
const terminal = ['succeeded', 'partial_failed', 'failed', 'cancelled', 'attention']
const current = computed(() => store.selectedWisersoneDownload)
const canCancel = computed(() => current.value && current.value.status !== 'cancelling' && !terminal.includes(current.value.status))
const canRetry = computed(() => current.value && ['partial_failed', 'failed', 'attention'].includes(current.value.status))
const canViewResult = computed(() => current.value?.campaign_id && terminal.includes(current.value.status))
let timer: ReturnType<typeof setInterval> | undefined
let inFlight = false

onMounted(() => {
  void store.loadWisersoneDownloads()
  timer = setInterval(async () => {
    if (inFlight) return
    inFlight = true
    try {
      await store.loadWisersoneDownloads()
      if (current.value && !terminal.includes(current.value.status)) await store.refreshWisersoneDownload()
    } finally { inFlight = false }
  }, 5000)
})
onBeforeUnmount(() => { if (timer !== undefined) clearInterval(timer) })
</script>

<template>
  <section
    class="wisersone-panel"
    aria-label="WisersOne 网站下载"
  >
    <p>在“采集策略 → 新建采集计划”中配置 WisersOne 计划、执行频率和品牌。计划到时下载过去 24 小时的 Excel 并自动导入；关闭此窗口不会停止服务器任务。</p>
    <label class="task-selector">
      查看已有任务
      <select
        :value="current?.id ?? ''"
        :disabled="store.actingWisersone"
        @change="store.selectWisersoneDownload(($event.target as HTMLSelectElement).value || null)"
      >
        <option value="">请选择要查看的任务</option>
        <option
          v-for="run in store.wisersoneDownloads"
          :key="run.id"
          :value="run.id"
        >
          {{ run.plan_name ?? '人工任务' }} · {{ formatDateTime(run.created_at) }} · {{ labels[run.status] }}
        </option>
      </select>
    </label>
    <p v-if="store.wisersoneDownloads.length === 0 && !store.wisersoneError">
      尚无下载任务，启用采集计划后会按执行频率自动运行。
    </p>
    <div
      v-if="current"
      class="task-state"
      role="status"
      aria-live="polite"
    >
      <strong>{{ labels[current.status] }}</strong>
      <small>任务 {{ current.id }}</small>
      <TaskProgressBar
        v-if="['submitting', 'waiting', 'downloading'].includes(current.status)"
        label="网站 Excel 生成进度"
        :value="current.percent"
        detail="网站生成完成后还会进行系统预检和入库。"
      />
      <p v-if="current.status === 'importing'">
        Excel 已保存，后台正在分批导入；完成后可查看导入结果。
      </p>
      <AimaFeedbackBanner
        v-if="current.error_code"
        tone="error"
        role="alert"
      >
        {{ current.status === 'attention' ? '提交结果未知，系统不会自动重复导出。请核对网站下载记录。' : '任务未全部完成，可恢复同一次任务。若登录态失效，请先更新宿主认证目录。' }}
        <small>错误代码：{{ current.error_code }}</small>
      </AimaFeedbackBanner>
      <div class="task-actions">
        <AimaButton
          v-if="canCancel"
          variant="secondary"
          :disabled="store.actingWisersone"
          @click="store.actWisersoneDownload('cancel')"
        >
          取消任务
        </AimaButton>
        <AimaButton
          v-if="canRetry"
          variant="secondary"
          :disabled="store.actingWisersone"
          @click="store.actWisersoneDownload('retry')"
        >
          恢复同一次任务
        </AimaButton>
        <AimaButton
          v-if="canViewResult"
          variant="primary"
          @click="emit('view-result', current.campaign_id!)"
        >
          查看导入结果
        </AimaButton>
      </div>
    </div>
    <AimaFeedbackBanner
      v-if="store.wisersoneError"
      tone="error"
      role="alert"
    >
      {{ store.wisersoneError }}
    </AimaFeedbackBanner>
  </section>
</template>

<style scoped>
.wisersone-panel, .task-state { display: grid; gap: var(--aima-space-3, 12px); }
.wisersone-panel p { margin: 0; line-height: 1.7; }
.task-selector { display: grid; gap: 8px; }
.task-selector select { width: 100%; padding: 8px; border: 1px solid var(--aima-border, #ddd); border-radius: 6px; }
.task-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.task-state small { display: block; overflow-wrap: anywhere; }
</style>
