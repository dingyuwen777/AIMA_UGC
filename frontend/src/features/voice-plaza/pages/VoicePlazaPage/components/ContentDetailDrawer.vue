<script setup lang="ts">
import type { ContentDetailResponse } from '../../../../../generated/api/client'
import { contentSummary, formatDateTime, formatNumber, labelPairText, platformLabel } from '../../../format'

defineProps<{ modelValue: boolean; item: ContentDetailResponse | null; loading: boolean }>()
defineEmits<{ 'update:modelValue': [open: boolean] }>()

function supplementTitle(status: string): string {
  if (status === 'failed') return '内容补充失败'
  if (status === 'partial_success') return '内容补充不完整'
  if (status === 'cancelled') return '内容补充已取消'
  return '内容补充进行中'
}

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
          <div><h2>内容详情</h2><small v-if="item">Content ID: {{ item.id }}</small></div><button
            type="button"
            aria-label="关闭"
            @click="$emit('update:modelValue', false)"
          >
            ×
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
              <span class="platform">{{ platformLabel(item.platform) }}</span><span class="analysis">{{ item.analysis.status === 'completed' ? item.analysis.sentiment || '已打标' : item.analysis.status === 'stale' ? '需重新打标' : '未打标' }}</span>
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
            <h4>AI 情感与全部标签</h4><div class="label-grid">
              <span
                v-for="(label, index) in item.analysis.labels ?? []"
                :key="`${label.primary_label}:${label.secondary_label}:${index}`"
              ><b>{{ label.primary_label }}</b><i>／</i>{{ label.secondary_label }}</span><em v-if="(item.analysis.labels ?? []).length === 0">暂无 AI 标签</em>
            </div><small v-if="item.analysis.analyzed_at">分析时间：{{ formatDateTime(item.analysis.analyzed_at) }} · {{ item.analysis.model_provider }} / {{ item.analysis.model }}</small>
          </section>

          <section v-if="(item.media ?? []).length > 0">
            <h4>原始内容媒体</h4><div class="media-grid">
              <a
                v-for="media in item.media ?? []"
                :key="`${media.position}:${media.url}`"
                :href="media.url || undefined"
                target="_blank"
                rel="noopener noreferrer"
              ><img
                v-if="media.preview_url"
                :src="media.preview_url"
                :alt="media.alt_text || '原始内容媒体预览'"
              ><span v-else>{{ media.media_type }} · 查看原始媒体</span></a>
            </div>
          </section>

          <section><h4>结构化信息</h4><dl><div><dt>平台</dt><dd>{{ platformLabel(item.platform) }}</dd></div><div><dt>作者</dt><dd>{{ item.author_display_name || '未知' }}</dd></div><div><dt>内容类型</dt><dd>{{ item.content_type }}</dd></div><div><dt>发布时间</dt><dd>{{ formatDateTime(item.published_at) }}</dd></div><div><dt>外部内容 ID</dt><dd>{{ item.external_content_id }}</dd></div><div><dt>来源</dt><dd>{{ item.source.provider_name }}</dd></div></dl></section>

          <section>
            <h4>互动数据</h4><div class="metric-grid">
              <span>点赞<b>{{ formatNumber(item.metrics.like_count) }}</b></span><span>评论<b>{{ formatNumber(item.metrics.comment_count) }}</b></span><span>分享<b>{{ formatNumber(item.metrics.share_count) }}</b></span><span>收藏<b>{{ formatNumber(item.metrics.favorite_count) }}</b></span><span>播放<b>{{ formatNumber(item.metrics.play_count) }}</b></span><span>浏览<b>{{ formatNumber(item.metrics.view_count) }}</b></span>
            </div>
          </section>

          <section>
            <h4>评论与覆盖</h4><p
              v-if="item.comment_coverage"
              class="coverage"
            >
              已采集 {{ formatNumber(item.comment_coverage.collected_count) }} / {{ formatNumber(item.comment_coverage.reported_total) }}，覆盖状态：{{ item.comment_coverage.coverage }}
            </p><div
              v-if="(item.comments ?? []).length"
              class="comments"
            >
              <article
                v-for="comment in item.comments ?? []"
                :key="comment.id"
              >
                <strong>{{ comment.author_display_name || '匿名用户' }}</strong><time>{{ formatDateTime(comment.published_at) }}</time><p>{{ comment.text || '无评论正文' }}</p>
              </article>
            </div><p
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
.backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgb(25 32 45 / 43%); }
.drawer { position: absolute; top: 0; right: 0; display: flex; width: min(610px, 46vw); height: 100%; flex-direction: column; background: #fff; box-shadow: -12px 0 36px rgb(31 39 55 / 12%); }
header { display: flex; min-height: 82px; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--aima-border); }
header h2 { margin: 0 0 5px; font-size: 20px; }
header small { color: #929aaa; }
header button { border: 0; color: #7b8494; background: transparent; font-size: 28px; cursor: pointer; }
.drawer-body { overflow-y: auto; padding: 22px 24px 36px; }
section { margin-bottom: 17px; padding: 17px; border: 1px solid var(--aima-border); border-radius: 9px; }
.hero { border: 0; padding: 4px 0 12px; }
.badges { display: flex; gap: 8px; }
.badges span { padding: 4px 8px; border-radius: 4px; font-size: 11px; }
.platform { color: #2765a3; background: #edf5ff; }
.analysis { color: #cc2f58; background: #fff0f5; }
.hero h3 { margin: 14px 0 9px; font-size: 20px; line-height: 1.45; }
.hero p, section p { color: #5f697b; font-size: 13px; line-height: 1.7; }
.hero a { color: var(--aima-primary); font-size: 12px; text-decoration: none; }
.supplement-status { border-color: #dfe5ee; background: #f7f9fc; }
.supplement-status h4 { margin-bottom: 6px; }
.supplement-status p { margin: 0; }
.supplement-status--failed { border-color: #f0cbd0; background: #fff7f8; }
.supplement-status--partial_success { border-color: #eadbbd; background: #fffbf2; }
.supplement-status--running, .supplement-status--queued { border-color: #ccdeef; background: #f5f9fd; }
h4 { margin: 0 0 13px; color: #30394a; font-size: 14px; }
.label-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 9px; }
.label-grid span { padding: 7px 9px; border: 1px solid #d9e6f7; border-radius: 5px; color: #396b9e; background: #f4f8fe; font-size: 12px; }
.label-grid b { color: #285b8d; }
.label-grid i { color: #8aa6c2; font-style: normal; }
.label-grid em, .empty { color: #969eac; font-size: 12px; font-style: normal; }
section > small { color: #8a93a3; font-size: 11px; }
dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 0; }
dl div { padding: 10px; border-radius: 6px; background: #f8f9fb; }
dt { color: #8a93a3; font-size: 10px; }
dd { overflow-wrap: anywhere; margin: 5px 0 0; color: #354052; font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.metric-grid span { padding: 10px; border-radius: 6px; color: #818a99; background: #f8f9fb; font-size: 10px; text-align: center; }
.metric-grid b { display: block; margin-top: 5px; color: #344052; font-size: 15px; }
.media-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.media-grid a { display: grid; min-height: 80px; place-items: center; overflow: hidden; border-radius: 7px; color: #536175; background: #f5f7fa; font-size: 12px; text-decoration: none; }
.media-grid img { width: 100%; height: 120px; object-fit: cover; }
.coverage { padding: 9px; border-radius: 5px; background: #f6f8fb; }
.comments article { padding: 10px 0; border-top: 1px solid #eef0f4; }
.comments strong { font-size: 12px; }
.comments time { float: right; color: #9aa1ae; font-size: 10px; }
.comments p { margin: 5px 0 0; }
.drawer-state { display: grid; flex: 1; place-items: center; color: #7f8899; }
</style>
