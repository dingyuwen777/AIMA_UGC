<script setup lang="ts">
import AimaFeedbackBanner from '../../shared/ui/AimaFeedbackBanner.vue'
import AimaButton from '../../shared/ui/AimaButton.vue'
import type { CollectionSupplementFormState } from './useCollectionSupplement'
const props = defineProps<{ state: CollectionSupplementFormState }>()
const labels = { xiaohongshu: '小红书', douyin: '抖音', weibo: '微博', bilibili: 'B站', kuaishou: '快手' }
function blockReason(reason: string): string {
  return ({ exact_resolution_unavailable: '分享链接无法确认内容', identity_conflict: '平台身份冲突', identity_unavailable: '缺少可验证的平台身份' } as Record<string, string>)[reason] ?? '平台身份不可用于补采'
}
</script>
<template>
  <section class="supplement-options">
    <label>采集渠道
      <select
        :value="props.state.providerConfigId"
        :disabled="state.creating"
        @change="state.setProvider(($event.target as HTMLSelectElement).value)"
      >
        <option value="">请选择采集渠道</option>
        <option
          v-for="item in state.capabilities?.provider_configs"
          :key="item.id"
          :value="item.id"
        >{{ item.display_name }}</option>
      </select>
    </label>
    <p
      v-if="state.loading"
      role="status"
    >
      正在核对补采目标…
    </p>
    <div class="platform-grid">
      <label
        v-for="item in state.preview?.platforms"
        :key="item.platform"
        class="platform-option"
      >
        <span><input
          type="checkbox"
          :checked="state.platforms.includes(item.platform)"
          :disabled="state.selected || (!state.platforms.includes(item.platform) && !state.supports(item.platform)) || state.creating"
          @change="state.togglePlatform(item.platform)"
        > {{ labels[item.platform] }} · {{ item.content_count }} 条</span>
        <small>可直接补采 {{ item.direct_target_count }} 条；待解析 {{ item.resolution_candidate_count }} 条；不可补采 {{ item.blocked_count }} 条</small>
        <small v-if="!state.supports(item.platform)">当前渠道不支持所选采集内容，请选择支持该平台的渠道。</small>
        <small
          v-for="(count, reason) in item.block_reasons"
          :key="reason"
        >{{ blockReason(reason) }}：{{ count }} 条，请检查原始内容链接或平台 ID。</small>
      </label>
    </div>
    <p
      v-if="state.preview"
      role="status"
    >
      已选 {{ state.platforms.length }} 个平台 · 预计处理 {{ state.platforms.length ? state.preview.target_count : 0 }} 条内容（含身份缺口）
    </p>
    <label><input
      type="checkbox"
      checked
      disabled
    > 内容详情 · 固定执行</label>
    <label><input
      :checked="props.state.includeComments"
      type="checkbox"
      :disabled="state.selected || state.creating"
      @change="state.setComments(($event.target as HTMLInputElement).checked)"
    > 评论{{ state.selected ? ' · 固定执行' : '' }}</label>
    <label><input
      :checked="props.state.includeSubComments"
      type="checkbox"
      :disabled="!state.includeComments || state.creating"
      @change="state.setSubComments(($event.target as HTMLInputElement).checked)"
    > 二级回复 · 默认采集</label>
    <AimaFeedbackBanner
      v-if="state.preview?.target_count === 0"
      tone="info"
    >
      当前范围没有可补采内容，请调整日期或选择。
    </AimaFeedbackBanner>
    <AimaFeedbackBanner
      v-if="state.error"
      tone="error"
      role="alert"
    >
      {{ state.error }} <AimaButton
        variant="text"
        size="small"
        :disabled="state.loading || state.creating"
        @click="state.refreshPreview()"
      >
        重新预览
      </AimaButton>
    </AimaFeedbackBanner>
    <AimaFeedbackBanner tone="warning">
      默认采集全部可访问的一级评论和二级回复，可能增加请求次数、费用和耗时；可取消二级回复。达到分页上限或接口不可访问时会标记采集缺口。
    </AimaFeedbackBanner>
  </section>
</template>
<style scoped>
.supplement-options { display: grid; gap: 14px; color: var(--aima-text-secondary); font-size: 13px; }
select { width: 100%; height: 34px; margin-top: 8px; border: 1px solid var(--aima-border-strong); border-radius: var(--aima-radius-lg); background: var(--aima-surface); color: var(--aima-text); }
.platform-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.platform-option { padding: 12px; border: 1px solid var(--aima-border); border-radius: var(--aima-radius-lg); }
.platform-option small { display: block; margin-top: 6px; color: var(--aima-text-muted); line-height: 18px; }
input { accent-color: var(--aima-primary); }
@media (max-width: 600px) { .platform-grid { grid-template-columns: 1fr; } }
</style>
