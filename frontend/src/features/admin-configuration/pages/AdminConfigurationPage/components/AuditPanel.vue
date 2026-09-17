<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { AuditEventResponse } from '../../../../../generated/api/client'
import { apiErrorMessage } from '../../../../../shared/api/http'
import { formatDateTime } from '../../../../../shared/domain/beijingTime'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { fetchAuditEvents } from '../../../api'
import {
  auditActionLabel,
  auditActorLabel,
  auditObjectLabel,
  auditSummaryText,
} from '../../../presentation'

const events = ref<AuditEventResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const total = ref(0)
const offset = ref(0)
const limit = 100

onMounted(load)

/** 读取当前审计页；如果当前页越界，则自动收敛到最后一页。 */
async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const response = await fetchAuditEvents(offset.value, limit)
    events.value = response.items
    total.value = response.total
    if (offset.value >= response.total && offset.value > 0) {
      offset.value = Math.max(0, Math.floor(Math.max(0, response.total - 1) / limit) * limit)
      const corrected = await fetchAuditEvents(offset.value, limit)
      events.value = corrected.items
      total.value = corrected.total
    }
  } catch (reason) {
    error.value = apiErrorMessage(reason)
  } finally {
    loading.value = false
  }
}

/** 返回上一页审计记录。 */
async function previousPage(): Promise<void> {
  offset.value = Math.max(0, offset.value - limit)
  await load()
}

/** 进入下一页审计记录。 */
async function nextPage(): Promise<void> {
  if (offset.value + limit >= total.value) return
  offset.value += limit
  await load()
}

/** 技术详情只格式化后端已经脱敏的安全摘要。 */
function safeJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <section
    class="card audit-card"
    aria-label="操作记录"
  >
    <header>
      <div>
        <h2>操作记录</h2>
        <p>展示谁在什么时候做了什么、影响了什么。技术信息按需展开。共 {{ total }} 条。</p>
      </div>
      <AimaButton
        size="small"
        :disabled="loading"
        @click="load"
      >
        刷新
      </AimaButton>
    </header>

    <AimaFeedbackBanner
      v-if="error"
      tone="error"
      role="alert"
    >
      <strong>操作记录读取失败</strong>
      <span>{{ error }}</span>
      <AimaButton
        variant="text"
        size="small"
        :disabled="loading"
        @click="load"
      >
        重试
      </AimaButton>
    </AimaFeedbackBanner>

    <div
      v-if="loading && events.length === 0"
      class="state-card"
    >
      正在读取操作记录…
    </div>

    <div
      v-else
      class="admin-table-scroll"
      role="region"
      aria-label="操作记录表格"
      tabindex="0"
    >
      <table>
        <colgroup>
          <col class="col-time">
          <col class="col-actor">
          <col class="col-action">
          <col class="col-object">
          <col class="col-summary">
          <col class="col-detail">
        </colgroup>
        <thead>
          <tr>
            <th>时间</th>
            <th>操作人</th>
            <th>操作</th>
            <th>影响对象</th>
            <th>操作说明</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="event in events"
            :key="event.id"
          >
            <td>{{ formatDateTime(event.created_at) }}</td>
            <td>{{ auditActorLabel(event.actor_ref) }}</td>
            <td>
              <strong>{{ auditActionLabel(event.event_type) }}</strong>
            </td>
            <td>{{ auditObjectLabel(event.object_type, event.object_id) }}</td>
            <td>{{ auditSummaryText(event) }}</td>
            <td>
              <details class="technical-details audit-details">
                <summary>技术详情</summary>
                <dl>
                  <div>
                    <dt>事件类型</dt>
                    <dd>{{ event.event_type }}</dd>
                  </div>
                  <div>
                    <dt>对象类型</dt>
                    <dd>{{ event.object_type ?? '—' }}</dd>
                  </div>
                  <div>
                    <dt>对象标识</dt>
                    <dd>{{ event.object_id ?? '—' }}</dd>
                  </div>
                  <div>
                    <dt>请求标识</dt>
                    <dd>{{ event.request_id ?? '—' }}</dd>
                  </div>
                </dl>
                <div class="raw-detail">
                  <strong>安全审计数据</strong>
                  <pre>{{ safeJson(event.safe_detail) }}</pre>
                </div>
              </details>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-if="!loading && total === 0 && !error"
      class="empty-state"
    >
      暂无操作记录。
    </p>

    <nav
      v-if="total > 0"
      class="audit-pagination"
      aria-label="操作记录分页"
    >
      <span>第 {{ Math.floor(offset / limit) + 1 }} / {{ Math.ceil(total / limit) }} 页 · 共 {{ total }} 条</span>
      <div>
        <AimaButton
          size="small"
          :disabled="loading || offset === 0"
          @click="previousPage"
        >
          上一页
        </AimaButton>
        <AimaButton
          size="small"
          :disabled="loading || offset + limit >= total"
          @click="nextPage"
        >
          下一页
        </AimaButton>
      </div>
    </nav>
  </section>
</template>

<style scoped>
.card {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--aima-border);
  border-radius: 8px;
  background: var(--aima-surface);
}
.audit-card { display: grid; gap: 14px; }
.audit-card > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
h2, p { margin: 0; }
h2 { color: var(--aima-text); font-size: 16px; font-weight: 500; line-height: 24px; }
.audit-card > header p { margin-top: 4px; color: var(--aima-text-muted); font-size: 11px; line-height: 16px; }
.state-card,
.empty-state { padding: 24px 12px; color: var(--aima-text-muted); text-align: center; font-size: 12px; }
.admin-table-scroll { min-width: 0; max-width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 1176px; table-layout: fixed; border-collapse: collapse; }
.col-time { width: 160px; }
.col-actor { width: 110px; }
.col-action { width: 160px; }
.col-object { width: 210px; }
.col-summary { width: 326px; }
.col-detail { width: 210px; }
thead tr { height: 40px; }
tbody tr { height: 74px; }
th, td {
  padding: 10px 8px;
  border-bottom: 1px solid var(--aima-border);
  overflow-wrap: anywhere;
  text-align: left;
  vertical-align: top;
}
th { color: var(--aima-text-muted); background: #fafbfc; font-size: 12px; font-weight: 500; line-height: 16px; }
td { color: var(--aima-text-secondary); font-size: 12px; line-height: 18px; }
.technical-details summary { cursor: pointer; color: var(--aima-text-secondary); font-size: 12px; }
.technical-details dl { display: grid; gap: 7px; margin: 10px 0 0; }
.technical-details dl div { display: grid; grid-template-columns: 80px minmax(0, 1fr); gap: 8px; }
.technical-details dt { color: var(--aima-text-disabled); font-size: 10px; }
.technical-details dd { margin: 0; overflow-wrap: anywhere; color: var(--aima-text-secondary); font-size: 11px; }
.raw-detail { margin-top: 10px; }
.raw-detail pre { max-height: 220px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.audit-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--aima-text-muted);
  font-size: 11px;
}
.audit-pagination > div { display: flex; gap: 8px; }
</style>
