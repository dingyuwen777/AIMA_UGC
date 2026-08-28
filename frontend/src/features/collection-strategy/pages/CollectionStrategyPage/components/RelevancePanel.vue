<script setup lang="ts">
import { ref, watch } from 'vue'

import type { GlobalRelevanceConfigResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import { formatBeijingDateTime } from '../../../presentation'

const props = defineProps<{
  packs: KeywordPackSummaryResponse[]
  relevance: GlobalRelevanceConfigResponse | null
  saving: boolean
}>()
const emit = defineEmits<{ save: [packId: string] }>()
const selectedId = ref('')

watch(
  () => props.relevance?.keyword_pack_id,
  (value) => { selectedId.value = value ?? props.packs[0]?.id ?? '' },
  { immediate: true },
)
</script>

<template>
  <section class="relevance-layout">
    <article>
      <div class="heading">
        <div><h2>全局规则相关性</h2><p>所有数据导入和周期采集共用一份关键词准入规则。</p></div><span>系统全局唯一</span>
      </div>
      <label>选择相关性词包<select v-model="selectedId"><option
        value=""
        disabled
      >请选择启用且非空的词包</option><option
        v-for="pack in packs"
        :key="pack.id"
        :value="pack.id"
      >{{ pack.name }} · v{{ pack.version }} · {{ pack.keyword_count }} 词</option></select></label>
      <AimaFeedbackBanner tone="info">
        采集计划执行时会冻结当时的词包版本和有效关键词，单个计划不可覆盖。
      </AimaFeedbackBanner>
      <AimaButton
        variant="primary"
        :disabled="saving || !selectedId || selectedId === relevance?.keyword_pack_id"
        @click="emit('save', selectedId)"
      >
        {{ saving ? '保存中…' : '保存全局配置' }}
      </AimaButton>
    </article>
    <aside>
      <template v-if="relevance">
        <span class="badge">已配置</span><h3>当前有效关键词</h3><p>词包 v{{ relevance.keyword_pack_version }} · 配置 v{{ relevance.version }}</p>
        <div class="keywords">
          <span
            v-for="keyword in relevance.effective_keywords"
            :key="keyword"
          >{{ keyword }}</span>
        </div>
        <small>更新时间：{{ formatBeijingDateTime(relevance.updated_at) }}</small>
      </template>
      <div
        v-else
        class="empty"
      >
        尚未配置全局相关性。正式导入与采集会保持关闭准入。
      </div>
    </aside>
  </section>
</template>

<style scoped>
.relevance-layout { display: grid; grid-template-columns: minmax(620px, 790px) minmax(330px, 400px); gap: 16px; }
article,aside { padding: 24px; border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.heading { display: flex; justify-content: space-between; }.heading h2 { margin: 0; font-size: 20px; }.heading p { margin: 7px 0 24px; color: #6f7a8e; }.heading > span { height: 26px; padding: 5px 9px; border-radius: 5px; color: #188252; background: #eaf8f1; font-size: 12px; }
label { display: block; color: #344054; font-weight: 600; }select { display: block; width: 100%; height: 43px; margin-top: 9px; padding: 0 12px; border: 1px solid #d9dee7; border-radius: 7px; background: #fff; }
.aima-feedback { margin: 18px 0; }
.badge { padding: 5px 9px; border-radius: 5px; color: #158653; background: #e9f8f0; font-size: 12px; }aside h3 { margin: 18px 0 4px; }aside p,aside small { color: #758095; }.keywords { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 24px; }.keywords span { padding: 7px 10px; border: 1px solid #cfe2f8; border-radius: 6px; color: #315a87; background: #f5f9ff; }
.empty { display: grid; min-height: 180px; place-items: center; color: #8a93a3; text-align: center; }
</style>
