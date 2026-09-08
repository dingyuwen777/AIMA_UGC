<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { KeywordPackKeywordCreateRequest, KeywordPackResponse } from '../../../../../generated/api/client'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaDialog from '../../../../../shared/ui/AimaDialog.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'
import { COLLECTION_PLATFORM_OPTIONS } from '../../../presentation'

const props = defineProps<{ saving: boolean; error?: string | null; initialPack?: KeywordPackResponse | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ submit: [name: string, description: string, keywords: KeywordPackKeywordCreateRequest[]] }>()
type DraftKeyword = KeywordPackKeywordCreateRequest & { key: number; original: boolean }
const name = ref('')
const description = ref('')
const keywordText = ref('')
const drafts = ref<DraftKeyword[]>([])
let nextKey = 0
const pendingWords = computed(() => [...new Set(keywordText.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean))]
  .filter((text) => !drafts.value.some((item) => item.text.trim() === text && item.platform_scope === 'all')))
const keywordCount = computed(() => drafts.value.length + pendingWords.value.length)
const invalid = computed(() => !name.value.trim() || (!props.initialPack && keywordCount.value === 0)
  || (!props.initialPack && keywordCount.value > 500) || drafts.value.some((item) => !item.text.trim() || !Number.isInteger(item.priority)))

/** 新建和编辑使用同一份草稿，编辑时冻结已读身份与完整成员属性。 */
watch(open, (value) => {
  if (!value) return
  name.value = props.initialPack?.name ?? ''
  description.value = props.initialPack?.description ?? ''
  keywordText.value = ''
  drafts.value = (props.initialPack?.keywords ?? []).map((item) => ({
    key: nextKey++, original: true, text: item.text, platform_scope: item.platform_scope,
    priority: item.priority, enabled: item.enabled, note: item.note,
  }))
}, { immediate: true })

function locked(item: DraftKeyword): boolean {
  return props.saving || (item.original && props.initialPack?.enabled === true)
}

/** 批量粘贴仅写入弹窗草稿，所有字段在底部保存时一次提交。 */
function addDrafts(): void {
  drafts.value.push(...pendingWords.value.map((text) => ({
    key: nextKey++, original: false, text, platform_scope: 'all' as const, priority: 100, enabled: true, note: '',
  })))
  keywordText.value = ''
}

function save(): void {
  if (invalid.value || props.saving) return
  addDrafts()
  emit('submit', name.value.trim(), description.value.trim(), drafts.value.map((item) => ({
    text: item.text.trim(), platform_scope: item.platform_scope, priority: item.priority,
    enabled: item.enabled, note: item.note ?? '',
  })))
}
</script>

<template>
  <AimaDialog
    v-model="open"
    :label="initialPack ? '编辑关键词包' : '新建关键词包'"
    width="630px"
    class="keyword-create-dialog"
  >
    <header>
      <div><h2>{{ initialPack ? '编辑关键词包' : '新建关键词包' }}</h2><p>保存词包名称、描述和关键词，可被多个采集计划复用</p></div>
      <AimaButton
        variant="text"
        aria-label="关闭"
        @click="open = false"
      >
        <AimaIcon name="close" />
      </AimaButton>
    </header>
    <div class="body">
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
      <label>词包名称<input
        v-model="name"
        :disabled="saving"
        maxlength="200"
        placeholder="例如：爱玛秋季新品"
      ></label>
      <label>描述<input
        v-model="description"
        :disabled="saving"
        maxlength="2000"
        placeholder="说明该词包的发现用途"
      ></label>
      <AimaFeedbackBanner
        v-if="initialPack?.enabled"
        tone="info"
      >
        此词包已启用，可以追加关键词；修改或移除已有关键词前须先停用。名称和描述仍可修改。
      </AimaFeedbackBanner>
      <section
        v-if="drafts.length"
        class="keyword-list"
        aria-label="关键词草稿"
      >
        <article
          v-for="(item, index) in drafts"
          :key="item.key"
          class="keyword-row"
        >
          <div class="keyword-title">
            <input
              v-model="item.text"
              :aria-label="`关键词 ${index + 1}`"
              :disabled="locked(item)"
              maxlength="500"
            >
            <AimaButton
              size="small"
              :disabled="locked(item)"
              :aria-label="`移除关键词 ${index + 1}`"
              @click="drafts.splice(index, 1)"
            >
              移除
            </AimaButton>
          </div>
          <details>
            <summary>平台、优先级与备注</summary>
            <div class="keyword-options">
              <label>适用平台<select
                v-model="item.platform_scope"
                aria-label="适用平台"
                :disabled="locked(item)"
              ><option value="all">全部平台</option><option
                v-for="option in COLLECTION_PLATFORM_OPTIONS"
                :key="option.value"
                :value="option.value"
              >{{ option.label }}</option></select></label>
              <label>优先级<input
                v-model.number="item.priority"
                :disabled="locked(item)"
                type="number"
                step="1"
              ></label>
              <label class="keyword-enabled"><input
                v-model="item.enabled"
                :disabled="locked(item)"
                type="checkbox"
              >启用该关键词</label>
              <label class="note">备注<input
                v-model="item.note"
                :disabled="locked(item)"
                maxlength="1000"
              ></label>
            </div>
          </details>
        </article>
      </section>
      <label>关键词（每行一个）<textarea
        v-model="keywordText"
        :disabled="saving"
        maxlength="12000"
        placeholder="爱玛 Q7&#10;爱玛电动车&#10;爱玛门店"
      /></label>
      <div class="draft-summary">
        <span>共 {{ keywordCount }} 条关键词；保存时统一提交。</span><AimaButton
          v-if="pendingWords.length"
          size="small"
          :disabled="saving"
          @click="addDrafts"
        >
          展开编辑属性
        </AimaButton>
      </div>
      <AimaFeedbackBanner
        v-if="!initialPack && keywordCount > 500"
        tone="error"
      >
        新建词包一次最多保存 500 条关键词，请减少后重试。
      </AimaFeedbackBanner>
    </div>
    <footer>
      <AimaButton @click="open = false">
        取消
      </AimaButton><AimaButton
        variant="primary"
        :disabled="saving || invalid"
        @click="save"
      >
        {{ saving ? '保存中…' : '保存词包' }}
      </AimaButton>
    </footer>
  </AimaDialog>
</template>

<style scoped>
:global(.keyword-create-dialog) { height: 526px; overflow: hidden; border: 0; border-radius: 10px; box-shadow: 0 20px 60px rgb(20 29 44 / 22%); }
:global(.keyword-create-dialog > .aima-dialog-body) { display: contents; }
header { display: flex; height: 68px; flex: none; align-items: flex-start; justify-content: space-between; padding: 24px 24px 0; }h2 { margin: 0; font-size: 19px; line-height: 22px; }header p { margin: 5px 0 0; color: #788397; font-size: 12px; line-height: 16px; }
.body { min-height: 0; flex: 1; overflow-y: auto; padding: 20px 24px 0; }label { display: block; margin-bottom: 16px; color: #344054; font-size: 13px; font-weight: 600; line-height: 16px; }input,textarea,select { display: block; width: 100%; margin-top: 7px; padding: 9px 11px; border: 1px solid #d9dfe8; border-radius: 6px; font-weight: 400; }input,select { height: 40px; }textarea { height: 120px; min-height: 120px; resize: vertical; }.body :deep(.aima-feedback) { margin-bottom: 14px; min-height: 38px; padding: 9px 13px; }
footer { display: flex; height: 76px; flex: none; align-items: flex-start; justify-content: flex-end; gap: 12px; padding: 20px 24px 24px; }footer :deep(.aima-button) { height: 32px; }footer :deep(.aima-button:first-child) { min-width: 68px; }footer :deep(.aima-button:last-child) { min-width: 96px; }
.keyword-list { display: grid; gap: 10px; margin-bottom: 16px; }.keyword-row { padding: 10px; border: 1px solid var(--aima-border); border-radius: 6px; }.keyword-title { display: flex; align-items: center; gap: 8px; }.keyword-title input { min-width: 0; flex: 1; margin: 0; }.keyword-row summary { margin-top: 8px; color: #788397; cursor: pointer; font-size: 11px; }.keyword-options { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }.keyword-options label { margin: 0; }.keyword-enabled { display: flex; align-items: center; gap: 6px; }.keyword-enabled input { width: 14px; height: 14px; margin: 0; }.note { grid-column: 1 / -1; }.draft-summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #788397; font-size: 12px; }input:disabled,select:disabled { color: #758094; background: #f7f9fc; }
</style>
