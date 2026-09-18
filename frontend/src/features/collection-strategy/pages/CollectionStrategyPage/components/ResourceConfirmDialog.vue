<script setup lang="ts">
import { computed } from 'vue'

import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'

interface ConfirmTarget {
  kind: 'keyword_pack' | 'plan'
  action: 'archive' | 'delete'
  name: string
}

const props = defineProps<{
  target: ConfirmTarget | null
  saving: boolean
  error?: string | null
}>()
const emit = defineEmits<{
  close: []
  confirm: []
}>()

const open = computed({
  get: () => props.target !== null,
  set: (value: boolean) => { if (!value) emit('close') },
})

const title = computed(() => {
  if (!props.target) return '确认操作'
  if (props.target.action === 'delete') {
    return props.target.kind === 'plan' ? '永久删除已归档采集计划' : '永久删除已归档词包'
  }
  return props.target.kind === 'plan' ? '确认归档采集计划' : '确认归档关键词包'
})

const message = computed(() => {
  if (!props.target) return ''
  if (props.target.action === 'delete') {
    return props.target.kind === 'plan'
      ? '只有系统确认该计划从未执行且没有历史引用时才能永久删除；删除后无法恢复。'
      : '只有系统确认该词包没有业务引用时才能永久删除；删除后无法恢复。'
  }
  return props.target.kind === 'plan'
    ? '归档后将停止未来调度，已经创建的历史运行不受影响。'
    : '归档后不会再出现在当前选择目录，历史任务使用过的配置保持不变。'
})

const confirmLabel = computed(() =>
  props.target?.action === 'delete' ? '永久删除' : '确认归档',
)
</script>

<template>
  <AimaModalContainer
    v-model="open"
    :label="title"
    width="540px"
    height="446px"
    close-on-backdrop
    :close-disabled="saving"
  >
    <template #header>
      <header>
        <div><h2>{{ title }}</h2><p v-if="target">{{ target.name }}</p></div>
        <AimaButton
          variant="text"
          aria-label="关闭"
          :disabled="saving"
          @click="emit('close')"
        >
          关闭
        </AimaButton>
      </header>
    </template>

    <div class="confirm-body">
      <p>{{ message }}</p>
      <AimaFeedbackBanner
        v-if="error"
        tone="error"
        role="alert"
      >
        {{ error }}
      </AimaFeedbackBanner>
    </div>

    <template #footer>
      <footer>
        <AimaButton
          :disabled="saving"
          @click="emit('close')"
        >
          取消
        </AimaButton><AimaButton
          variant="primary"
          :disabled="saving"
          @click="emit('confirm')"
        >
          {{ saving ? '处理中…' : confirmLabel }}
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>
</template>

<style scoped>
header { display: flex; min-height: 84px; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 24px; border-bottom: 1px solid var(--aima-border); }
h2 { margin: 0; color: var(--aima-text); font-size: 19px; line-height: 26px; }header p { margin: 5px 0 0; color: var(--aima-text-secondary); font-size: 12px; }
.confirm-body { display: grid; align-content: start; gap: 18px; min-height: 250px; padding: 28px 24px; }.confirm-body > p { margin: 0; color: var(--aima-text-secondary); font-size: 13px; line-height: 22px; }
footer { display: flex; height: 76px; align-items: center; justify-content: flex-end; gap: 8px; padding: 16px 24px; border-top: 1px solid var(--aima-border); }
</style>
