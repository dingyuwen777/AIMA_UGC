<script setup lang="ts">
defineProps<{ policy: 'adaptive' | 'full' }>()
</script>

<template>
  <div class="comment-policy-summary">
    <template v-if="policy === 'adaptive'">
      <p>一级评论不超过 50 条时全部采集；超过 50 条时以 50 条为采样目标。每条一级评论最多以 5 条回复为采样目标。</p>
      <p>评论数量没有变化时跳过；数量增加时，小红书与哔哩哔哩优先按可靠最新排序增量采集，其他平台受控刷新。</p>
      <p>采样会保留已请求整页的数据，因此实际数量可能略超目标；采样不代表全部评论已采完整。</p>
    </template>
    <template v-else>
      <p>持续翻页采集全部可获取的一级评论与回复，数量未知时也继续读取到接口结束。</p>
      <p>只有一级评论及所有必要回复都采完整、且评论数量未变时才跳过；不完整会继续补齐。已完整回复且数量未变时复用已有结果。</p>
      <p>数量增加时，小红书与哔哩哔哩在证据充分时沿用增量；其他平台完整刷新并按评论身份去重。</p>
      <p>全量受平台接口可见性限制；一级评论和每条回复线程各有 100 页安全上限。触及上限或分页异常会标记部分完成。</p>
    </template>
  </div>
</template>

<style scoped>
.comment-policy-summary { color: var(--aima-text-secondary); font-size: 12px; line-height: 20px; }
p { margin: 0 0 8px; }
p:last-child { margin-bottom: 0; }
</style>
