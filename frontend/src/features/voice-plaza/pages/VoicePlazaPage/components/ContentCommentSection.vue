<script setup lang="ts">
import { computed } from 'vue'

import type { ContentCommentResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import { formatDateTime, formatNumber } from '../../../format'
import type { CommentReplyState } from '../../../store'

const props = defineProps<{
  roots: ContentCommentResponse[]
  replies: Record<string, ContentCommentResponse[]>
  replyStates: Record<string, CommentReplyState>
  loading: boolean
  loadingNext: boolean
  error: string | null
  hasMore: boolean
  rootTotalCount: number
  ingestedTotalCount: number
  providerTotalCount?: number | null
  coverage?: string | null
}>()

const emit = defineEmits<{
  retry: []
  'load-more-roots': []
  'load-replies': [rootCommentId: string, reset: boolean]
}>()

const loadedCount = computed(() =>
  props.roots.length
  + Object.values(props.replies).reduce((total, items) => total + items.length, 0),
)

function replyState(rootCommentId: string): CommentReplyState | undefined {
  return props.replyStates[rootCommentId]
}

function replyItems(rootCommentId: string): ContentCommentResponse[] {
  return props.replies[rootCommentId] ?? []
}

function replyTarget(comment: ContentCommentResponse): string {
  if (comment.parent_author_display_name) return `回复 ${comment.parent_author_display_name}`
  if (comment.parent_comment_id) return '回复该线程中的评论'
  return '回复这条一级评论'
}

function replyButtonLabel(root: ContentCommentResponse): string {
  const state = replyState(root.external_comment_id)
  if (state?.loading) return '正在加载回复…'
  if (state?.error) return '重新加载回复'
  if (!state?.loaded) return `查看 ${formatNumber(root.ingested_reply_count ?? 0)} 条回复`
  if (state.hasMore) return `继续加载回复（已显示 ${replyItems(root.external_comment_id).length} / ${formatNumber(state.totalCount)}）`
  return `已显示全部 ${formatNumber(state.totalCount)} 条回复`
}

function coverageLabel(value?: string | null): string {
  if (value === 'complete') return '本次采集已完成'
  if (value === 'partial') return '本次采集到部分评论'
  if (value === 'unavailable') return '平台暂未提供评论'
  return '采集完整度待确认'
}
</script>

<template>
  <section class="comment-section">
    <div class="comment-heading">
      <div>
        <h4>评论</h4>
        <p>{{ coverageLabel(coverage) }}</p>
      </div>
      <div
        class="comment-counts"
        aria-label="评论数量"
      >
        <span>平台显示 <b>{{ providerTotalCount == null ? '未提供' : formatNumber(providerTotalCount) }}</b></span>
        <span>已采集 <b>{{ formatNumber(ingestedTotalCount) }}</b></span>
        <span>当前显示 <b>{{ formatNumber(loadedCount) }}</b></span>
      </div>
    </div>

    <div
      v-if="loading && roots.length === 0"
      class="comment-state"
    >
      正在加载评论…
    </div>
    <div
      v-else-if="error && roots.length === 0"
      class="comment-state comment-state--error"
      role="alert"
    >
      <p>评论暂时加载失败：{{ error }}</p>
      <AimaButton
        size="small"
        @click="emit('retry')"
      >
        重新加载评论
      </AimaButton>
    </div>
    <p
      v-else-if="roots.length === 0"
      class="comment-state"
    >
      暂无已采集评论。
    </p>

    <div
      v-else
      class="comment-threads"
    >
      <article
        v-for="root in roots"
        :key="root.id"
        class="comment-thread"
      >
        <div class="root-comment">
          <div class="comment-meta">
            <strong>{{ root.author_display_name || '匿名用户' }}</strong>
            <span
              v-if="root.is_by_content_author"
              class="author-badge"
            >原作者</span>
            <time>{{ formatDateTime(root.published_at) }}</time>
          </div>
          <p>{{ root.text || '该评论没有正文。' }}</p>
        </div>

        <div
          v-if="replyItems(root.external_comment_id).length"
          class="comment-replies"
        >
          <article
            v-for="reply in replyItems(root.external_comment_id)"
            :key="reply.id"
            class="reply-comment"
          >
            <div class="comment-meta">
              <strong>{{ reply.author_display_name || '匿名用户' }}</strong>
              <span
                v-if="reply.is_by_content_author"
                class="author-badge"
              >原作者</span>
              <time>{{ formatDateTime(reply.published_at) }}</time>
            </div>
            <small>{{ replyTarget(reply) }}</small>
            <p>{{ reply.text || '该回复没有正文。' }}</p>
          </article>
        </div>

        <p
          v-if="replyState(root.external_comment_id)?.error"
          class="reply-error"
          role="alert"
        >
          回复加载失败：{{ replyState(root.external_comment_id)?.error }}
        </p>
        <AimaButton
          v-if="(root.ingested_reply_count ?? 0) > 0"
          class="reply-button"
          size="small"
          :disabled="replyState(root.external_comment_id)?.loaded && !replyState(root.external_comment_id)?.hasMore && !replyState(root.external_comment_id)?.error"
          @click="emit('load-replies', root.external_comment_id, Boolean(replyState(root.external_comment_id)?.error))"
        >
          {{ replyButtonLabel(root) }}
        </AimaButton>
      </article>
    </div>

    <div
      v-if="roots.length"
      class="comment-pagination"
    >
      <span>已显示 {{ roots.length }} / {{ formatNumber(rootTotalCount) }} 条一级评论</span>
      <AimaButton
        size="small"
        :disabled="!hasMore || loadingNext"
        @click="emit('load-more-roots')"
      >
        {{ loadingNext ? '正在加载…' : hasMore ? '加载更多一级评论' : '一级评论已全部显示' }}
      </AimaButton>
    </div>
    <p
      v-if="error && roots.length"
      class="comment-page-error"
      role="alert"
    >
      更多评论加载失败：{{ error }}
    </p>
  </section>
</template>

<style scoped>
.comment-section { display: grid; gap: 14px; }
.comment-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.comment-heading h4 { margin: 0 0 3px; font-size: 16px; }
.comment-heading p { margin: 0; color: var(--aima-text-disabled); font-size: 11px; }
.comment-counts { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.comment-counts span { padding: 5px 8px; border-radius: 5px; color: var(--aima-text-muted); background: #f7f9fb; font-size: 10px; }
.comment-counts b { margin-left: 3px; color: var(--aima-text); }
.comment-state { display: grid; min-height: 72px; place-items: center; gap: 8px; margin: 0; border-radius: 7px; color: var(--aima-text-disabled); background: #f7f9fb; font-size: 12px; }
.comment-state p { margin: 0; }
.comment-state--error,
.comment-page-error,
.reply-error { color: var(--aima-danger); }
.comment-threads { display: grid; gap: 14px; }
.comment-thread { display: grid; gap: 9px; padding: 14px; border: 1px solid var(--aima-border); border-radius: 8px; background: white; }
.root-comment,
.reply-comment { display: grid; gap: 5px; }
.comment-meta { display: flex; min-width: 0; align-items: center; gap: 7px; }
.comment-meta strong { overflow: hidden; color: var(--aima-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.comment-meta time { margin-left: auto; color: var(--aima-text-disabled); font-size: 10px; }
.author-badge { padding: 2px 6px; border-radius: 999px; color: var(--aima-primary); background: var(--aima-primary-soft); font-size: 9px; }
.root-comment p,
.reply-comment p { margin: 0; color: var(--aima-text-secondary); font-size: 12px; line-height: 19px; white-space: pre-wrap; overflow-wrap: anywhere; }
.comment-replies { display: grid; gap: 10px; margin-left: 24px; padding: 11px 12px; border-left: 3px solid #e2e7ef; border-radius: 0 7px 7px 0; background: #f7f9fb; }
.reply-comment + .reply-comment { padding-top: 10px; border-top: 1px solid #e7ebf1; }
.reply-comment small { color: var(--aima-primary); font-size: 10px; }
.reply-button { justify-self: start; }
.reply-error,
.comment-page-error { margin: 0; font-size: 11px; }
.comment-pagination { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.comment-pagination span { color: var(--aima-text-disabled); font-size: 10px; }
@media (max-width: 680px) {
  .comment-heading,
  .comment-pagination { align-items: stretch; flex-direction: column; }
  .comment-counts { justify-content: flex-start; }
  .comment-replies { margin-left: 12px; }
}
</style>
