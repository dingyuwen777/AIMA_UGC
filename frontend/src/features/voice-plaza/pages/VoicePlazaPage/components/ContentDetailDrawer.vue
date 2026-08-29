<script setup lang="ts">
import type { ContentDetailResponse } from '../../../../../generated/api/client'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { contentSummary, formatDateTime, formatNumber, labelPairText, platformLabel } from '../../../format'

defineProps<{ modelValue: boolean; item: ContentDetailResponse | null; loading: boolean }>()
defineEmits<{ 'update:modelValue': [open: boolean] }>()

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
            <div class="label-grid">
              <span
                v-for="(label, index) in item.analysis.labels ?? []"
                :key="`${label.primary_label}:${label.secondary_label}:${index}`"
              >{{ labelPairText(label).replace(' / ', ' ／ ') }}</span>
              <em v-if="(item.analysis.labels ?? []).length === 0">暂无 AI 标签</em>
            </div>
            <small v-if="item.analysis.analyzed_at">分析时间：{{ formatDateTime(item.analysis.analyzed_at) }} · {{ item.analysis.model_provider }} / {{ item.analysis.model }}</small>
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
.label-grid { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 9px; }
.label-grid span { padding: 3px 8px; border-radius: 4px; color: #396b9e; background: #e8f3ff; font-size: 11px; }
.label-grid em,
.empty { color: var(--aima-text-disabled); font-size: 11px; font-style: normal; }
.drawer-body section > small { color: var(--aima-text-disabled); font-size: 10px; }
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
