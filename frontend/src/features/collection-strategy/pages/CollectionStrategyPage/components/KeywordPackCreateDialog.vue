<script setup lang="ts">
import { computed, ref, watch } from 'vue'

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
        <div><h2>新建 Discovery 词包</h2><p>保存后可被多个周期采集计划复用</p></div><button
          type="button"
          aria-label="关闭"
          @click="open = false"
        >
          ×
        </button>
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
        ></label><label>Discovery 关键词（每行一个）<textarea
          v-model="keywordText"
          maxlength="12000"
          placeholder="爱玛 Q7&#10;爱玛电动车&#10;爱玛门店"
        /></label><div class="tip">
          已识别 {{ keywords.length }} 个去重关键词；数据库仍会按正式 normalization 处理。
        </div>
      </div>
      <footer>
        <button
          type="button"
          @click="open = false"
        >
          取消
        </button><button
          class="primary"
          type="button"
          :disabled="saving || !name.trim() || keywords.length === 0"
          @click="emit('submit', name.trim(), description.trim(), keywords)"
        >
          {{ saving ? '保存中…' : '保存词包' }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; z-index: 110; inset: 0; display: grid; place-items: center; background: rgb(20 29 44 / 38%); }section { width: 540px; border-radius: 10px; background: #fff; box-shadow: 0 20px 60px rgb(20 29 44 / 22%); }header { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--aima-border); }h2 { margin: 0; font-size: 19px; }header p { margin: 5px 0 0; color: #788397; font-size: 12px; }header button { border: 0; background: transparent; font-size: 26px; cursor: pointer; }.body { padding: 20px 22px; }label { display: block; margin-bottom: 16px; color: #344054; font-size: 13px; font-weight: 600; }input,textarea { display: block; width: 100%; margin-top: 7px; padding: 9px 11px; border: 1px solid #d9dfe8; border-radius: 6px; font-weight: 400; }input { height: 40px; }textarea { min-height: 150px; resize: vertical; }.tip { padding: 10px 12px; border-radius: 6px; color: #1769c7; background: #f0f7ff; font-size: 12px; }footer { display: flex; justify-content: flex-end; gap: 10px; padding: 15px 22px; border-top: 1px solid var(--aima-border); }footer button { height: 39px; padding: 0 20px; border: 1px solid #d9dee7; border-radius: 6px; background: #fff; cursor: pointer; }.primary { border-color: var(--aima-primary) !important; color: #fff; background: var(--aima-primary) !important; }.primary:disabled { opacity: .5; }
</style>
