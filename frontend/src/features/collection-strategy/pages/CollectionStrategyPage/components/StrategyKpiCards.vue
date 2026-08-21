<script setup lang="ts">
import type { GlobalRelevanceConfigResponse } from '../../../../../generated/api/client'

defineProps<{
  packCount: number
  relevance: GlobalRelevanceConfigResponse | null
  enabledPlanCount: number
  relevancePackName: string
  loading: boolean
}>()
</script>

<template>
  <section
    class="kpis"
    aria-label="采集策略摘要"
  >
    <article><span class="icon blue">⌕</span><div><p>Discovery 词包</p><strong>{{ loading ? '—' : packCount }}</strong></div></article>
    <article><span class="icon green">◎</span><div><p>全局相关性</p><strong class="success">{{ relevance ? '已启用' : '待配置' }}</strong><small v-if="relevance">{{ relevancePackName }} · v{{ relevance.keyword_pack_version }}</small></div></article>
    <article><span class="icon purple">▣</span><div><p>启用计划</p><strong>{{ loading ? '—' : enabledPlanCount }}</strong></div></article>
  </section>
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 22px 0; }
article { display: flex; min-height: 118px; align-items: center; gap: 20px; padding: 22px; border: 1px solid var(--aima-border); border-radius: 10px; background: #fff; }
.icon { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 50%; color: #fff; font-size: 24px; }
.blue { background: #1473e6; } .green { background: #17a55f; } .purple { background: #7c3aed; }
p { margin: 0 0 6px; color: #637086; font-size: 14px; }
strong { color: #162033; font-size: 27px; font-weight: 600; }
.success { color: #15965a; font-size: 21px; }
small { display: block; margin-top: 6px; color: #6d7789; }
</style>
