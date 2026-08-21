<script setup lang="ts">
import { ref, watch } from 'vue'

import type { GlobalRelevanceConfigResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'

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
        <div><h2>系统全局相关性</h2><p>所有 Excel、TikHub 与未来采集来源共用一份 Relevance 准入配置。</p></div><span>系统全局唯一</span>
      </div>
      <label>选择 Relevance 词包<select v-model="selectedId"><option
        value=""
        disabled
      >请选择启用且非空的词包</option><option
        v-for="pack in packs"
        :key="pack.id"
        :value="pack.id"
      >{{ pack.name }} · v{{ pack.version }} · {{ pack.keyword_count }} 词</option></select></label>
      <div class="notice">
        Plan 运行时自动冻结当时的全局 Relevance Pack、版本和有效关键词，不能被单个 Plan 覆盖。
      </div>
      <button
        type="button"
        :disabled="saving || !selectedId || selectedId === relevance?.keyword_pack_id"
        @click="emit('save', selectedId)"
      >
        {{ saving ? '保存中…' : '保存全局配置' }}
      </button>
    </article>
    <aside>
      <template v-if="relevance">
        <span class="badge">已启用</span><h3>当前有效关键词</h3><p>Pack v{{ relevance.keyword_pack_version }} · Config v{{ relevance.version }}</p>
        <div class="keywords">
          <span
            v-for="keyword in relevance.effective_keywords"
            :key="keyword"
          >{{ keyword }}</span>
        </div>
        <small>更新时间：{{ new Date(relevance.updated_at).toLocaleString('zh-CN') }}</small>
      </template>
      <div
        v-else
        class="empty"
      >
        尚未配置全局 Relevance。正式 Import/Collection 会保持 fail closed。
      </div>
    </aside>
  </section>
</template>

<style scoped>
.relevance-layout { display: grid; grid-template-columns: minmax(620px, 1fr) 370px; gap: 16px; }
article,aside { padding: 24px; border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.heading { display: flex; justify-content: space-between; }.heading h2 { margin: 0; font-size: 20px; }.heading p { margin: 7px 0 24px; color: #6f7a8e; }.heading > span { height: 26px; padding: 5px 9px; border-radius: 5px; color: #188252; background: #eaf8f1; font-size: 12px; }
label { display: block; color: #344054; font-weight: 600; }select { display: block; width: 100%; height: 43px; margin-top: 9px; padding: 0 12px; border: 1px solid #d9dee7; border-radius: 7px; background: #fff; }
.notice { margin: 18px 0; padding: 12px 14px; border: 1px solid #b9d7ff; border-radius: 7px; color: #1f65bd; background: #f1f7ff; font-size: 13px; }
button { height: 42px; padding: 0 20px; border: 0; border-radius: 7px; color: #fff; background: var(--aima-primary); cursor: pointer; }button:disabled { opacity: .5; cursor: default; }
.badge { padding: 5px 9px; border-radius: 5px; color: #158653; background: #e9f8f0; font-size: 12px; }aside h3 { margin: 18px 0 4px; }aside p,aside small { color: #758095; }.keywords { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 24px; }.keywords span { padding: 7px 10px; border: 1px solid #cfe2f8; border-radius: 6px; color: #315a87; background: #f5f9ff; }
.empty { display: grid; min-height: 180px; place-items: center; color: #8a93a3; text-align: center; }
</style>
