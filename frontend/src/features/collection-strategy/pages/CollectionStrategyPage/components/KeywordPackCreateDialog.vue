<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaIcon from '../../../../../shared/ui/AimaIcon.vue'

defineProps<{ saving: boolean }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ submit: [name: string, description: string, keywords: string[]] }>()
const name = ref('')
const description = ref('')
const keywordText = ref('')
const keywords = computed(() =>
  [...new Set(keywordText.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean))],
)

watch(open, (value) => {
  if (!value) return
  name.value = ''
  description.value = ''
  keywordText.value = ''
})
</script>

<template>
  <div
    v-if="open"
    class="backdrop"
    @click.self="open = false"
  >
    <section
      role="dialog"
      aria-label="新建关键词包"
      aria-modal="true"
    >
      <header>
        <div><h2>新建关键词包</h2><p>保存后可被多个采集计划复用</p></div><AimaButton
          variant="text"
          aria-label="关闭"
          @click="open = false"
        >
          <AimaIcon name="close" />
        </AimaButton>
      </header>
      <div class="body">
        <label>词包名称<input
          v-model="name"
          maxlength="200"
          placeholder="例如：爱玛秋季新品"
        ></label><label>描述<input
          v-model="description"
          maxlength="2000"
          placeholder="说明该词包的发现用途"
        ></label><label>关键词（每行一个）<textarea
          v-model="keywordText"
          maxlength="12000"
          placeholder="爱玛 Q7&#10;爱玛电动车&#10;爱玛门店"
        /></label><AimaFeedbackBanner tone="info">
          已识别 {{ keywords.length }} 个去重关键词；保存时仍由后端执行正式标准化。
        </AimaFeedbackBanner>
      </div>
      <footer>
        <AimaButton
          @click="open = false"
        >
          取消
        </AimaButton><AimaButton
          variant="primary"
          :disabled="saving || !name.trim() || keywords.length === 0"
          @click="emit('submit', name.trim(), description.trim(), keywords)"
        >
          {{ saving ? '保存中…' : '保存词包' }}
        </AimaButton>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 110; inset: 0; display: grid; place-items: center; background: rgb(20 29 44 / 38%); }section { width: 630px; border-radius: 10px; background: #fff; box-shadow: 0 20px 60px rgb(20 29 44 / 22%); }header { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--aima-border); }h2 { margin: 0; font-size: 19px; }header p { margin: 5px 0 0; color: #788397; font-size: 12px; }.body { padding: 20px 22px; }label { display: block; margin-bottom: 16px; color: #344054; font-size: 13px; font-weight: 600; }input,textarea { display: block; width: 100%; margin-top: 7px; padding: 9px 11px; border: 1px solid #d9dfe8; border-radius: 6px; font-weight: 400; }input { height: 40px; }textarea { min-height: 150px; resize: vertical; }footer { display: flex; justify-content: flex-end; gap: 10px; padding: 15px 22px; border-top: 1px solid var(--aima-border); }
</style>
