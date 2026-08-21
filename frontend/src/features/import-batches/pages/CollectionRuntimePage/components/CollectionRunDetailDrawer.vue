<script setup lang="ts">
import type { CollectionRunResponse } from '../../../../../generated/api/client'
import {
  elapsed,
  formatDateTime,
  formatNumber,
  platformLabels,
  runtimeStageLabel,
  runtimeStatusLabels,
  shortId,
} from '../../../format'

defineProps<{ modelValue: boolean; item: CollectionRunResponse | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  refresh: []
  copy: [value: string]
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="drawer-layer"
      @click.self="emit('update:modelValue', false)"
    >
      <aside
        class="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="TikHub 运行详情"
      >
        <template v-if="item">
          <header>
            <strong>TikHub 运行详情</strong><button
              type="button"
              aria-label="关闭详情"
              @click="emit('update:modelValue', false)"
            >
              ×
            </button>
          </header>
          <div class="title-row">
            <div><span>{{ item.mode === 'discovery' ? '独立发现新内容' : '基于已有批次补采' }}</span><h2>{{ item.keywords?.length ? item.keywords.join(' / ') : '批次内容补采' }}</h2></div>
            <b :class="`status status--${item.status}`">{{ runtimeStatusLabels[item.status] }}</b>
          </div>
          <section class="facts">
            <div>
              <span>Run ID</span><strong>{{ shortId(item.run_id) }} <button
                type="button"
                @click="emit('copy', item.run_id)"
              >▢</button></strong>
            </div>
            <div>
              <span>Job ID</span><strong>{{ shortId(item.job_id) }} <button
                type="button"
                @click="emit('copy', item.job_id)"
              >▢</button></strong>
            </div>
            <div><span>目标平台</span><strong>{{ item.platforms.map((platform) => platformLabels[platform]).join(' / ') }}</strong></div>
            <div><span>关联 Batch</span><strong>{{ item.import_batch_id ? shortId(item.import_batch_id) : '—' }}</strong></div>
            <div><span>Attempt</span><strong>{{ item.attempt }} / {{ item.max_attempts }}</strong></div>
            <div><span>总耗时</span><strong>{{ elapsed(item.started_at, item.finished_at) }}</strong></div>
          </section>
          <section class="progress-panel">
            <div><strong>{{ runtimeStageLabel(item.stage) }}</strong><span>{{ item.progress }}%</span></div>
            <div class="track">
              <span :style="{ width: `${item.progress}%` }" />
            </div>
          </section>
          <h3>处理统计</h3>
          <section class="stats">
            <div><span>请求</span><strong>{{ formatNumber(item.stats.requested_count) }}</strong></div>
            <div><span>成功</span><strong>{{ formatNumber(item.stats.succeeded_count) }}</strong></div>
            <div><span>失败</span><strong>{{ formatNumber(item.stats.failed_count) }}</strong></div>
            <div><span>内容</span><strong>{{ formatNumber(item.stats.content_count) }}</strong></div>
            <div><span>评论</span><strong>{{ formatNumber(item.stats.comment_count) }}</strong></div>
            <div><span>相关性过滤</span><strong>{{ formatNumber(item.stats.filtered_count) }}</strong></div>
          </section>
          <h3>Scope 状态</h3>
          <section class="scopes">
            <div
              v-for="scope in item.scopes"
              :key="scope.id"
            >
              <i :class="`dot dot--${scope.status}`" /><span>{{ platformLabels[scope.platform] }} · {{ runtimeStageLabel(scope.operation_group) }}</span><strong>{{ scope.progress }}%</strong>
            </div>
          </section>
          <div
            v-if="item.error_summary"
            class="error-card"
          >
            <strong>{{ item.error_code || 'collection_run_failed' }}</strong><p>{{ item.error_summary }}</p>
          </div>
          <p class="info-note">
            详情每 5 秒自动刷新；关闭页面后 Durable Job 仍由 Worker 持续执行。
          </p>
          <footer>
            <span>创建于 {{ formatDateTime(item.created_at) }}</span><button
              type="button"
              @click="emit('refresh')"
            >
              刷新详情
            </button>
          </footer>
        </template>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-layer { position: fixed; inset: 0; z-index: 100; background: rgb(22 29 43 / 40%); }
.drawer { position: absolute; inset: 0 0 0 auto; width: 500px; overflow-y: auto; padding: 0 22px 86px; background: #fff; box-shadow: -10px 0 30px rgb(23 32 51 / 12%); }
header { display: flex; height: 60px; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--aima-border); }
header strong { font-size: 17px; }
header button { border: 0; color: #475166; background: transparent; cursor: pointer; font-size: 25px; }
.title-row { display: flex; align-items: flex-start; justify-content: space-between; margin: 18px 0 14px; }
.title-row span { color: #7b8496; font-size: 12px; }
.title-row h2 { max-width: 330px; margin: 6px 0 0; font-size: 18px; }
.status { padding: 5px 8px; border-radius: 5px; color: #2563eb; background: #eef4ff; font-size: 11px; }
.status--succeeded { color: #12804b; background: #eaf8f1; }
.status--failed { color: #d62f3a; background: #fff0f1; }
.status--partial_success { color: #b54708; background: #fff3e8; }
.facts { display: grid; grid-template-columns: 1fr 1fr; overflow: hidden; border: 1px solid var(--aima-border); border-radius: 8px; }
.facts > div { min-height: 68px; padding: 12px; border-right: 1px solid var(--aima-border); border-bottom: 1px solid var(--aima-border); }
.facts > div:nth-child(2n) { border-right: 0; }
.facts > div:nth-last-child(-n + 2) { border-bottom: 0; }
.facts span, .facts strong { display: block; }
.facts span { color: #778093; font-size: 11px; }
.facts strong { overflow: hidden; margin-top: 7px; color: #263043; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.facts button { border: 0; color: #687386; background: transparent; cursor: pointer; }
.progress-panel { margin: 14px 0; padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; }
.progress-panel > div:first-child { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 12px; }
.track { height: 7px; overflow: hidden; border-radius: 5px; background: #edf1f7; }
.track span { display: block; height: 100%; border-radius: inherit; background: #2563eb; }
h3 { margin: 18px 0 11px; font-size: 14px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
.stats div { padding: 11px 6px; border: 1px solid var(--aima-border); border-radius: 6px; text-align: center; }
.stats span, .stats strong { display: block; }
.stats span { color: #737c8d; font-size: 10px; }
.stats strong { margin-top: 5px; color: #2563eb; }
.scopes { border: 1px solid var(--aima-border); border-radius: 7px; }
.scopes div { display: grid; grid-template-columns: 20px 1fr auto; min-height: 42px; align-items: center; padding: 0 12px; border-bottom: 1px solid var(--aima-border); font-size: 12px; }
.scopes div:last-child { border-bottom: 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
.dot--running, .dot--queued { background: #2563eb; }
.dot--succeeded { background: #16a05d; }
.dot--failed { background: #e5484d; }
.error-card { margin-top: 16px; padding: 13px; border: 1px solid #ffc7cc; border-radius: 7px; color: #b4232d; background: #fff5f6; font-size: 12px; }
.error-card p { margin-bottom: 0; }
.info-note { padding: 12px; border: 1px solid #bcd5ff; border-radius: 6px; color: #2563eb; background: #f1f6ff; font-size: 11px; }
footer { position: absolute; right: 0; bottom: 0; left: 0; display: flex; height: 70px; align-items: center; justify-content: space-between; padding: 0 22px; border-top: 1px solid var(--aima-border); background: #fff; color: #7b8496; font-size: 11px; }
footer button { height: 40px; padding: 0 28px; border: 1px solid var(--aima-primary); border-radius: 6px; color: #fff; background: var(--aima-primary); cursor: pointer; }
</style>
