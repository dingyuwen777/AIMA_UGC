<script setup lang="ts">
import { computed } from 'vue'
import type { CollectionRunCreatedResponse, CollectionSupplementTargetSelection } from '../../../../../generated/api/client'
import AimaModalContainer from '../../../../../shared/ui/AimaModalContainer.vue'
import AimaButton from '../../../../../shared/ui/AimaButton.vue'
import AimaFeedbackBanner from '../../../../../shared/ui/AimaFeedbackBanner.vue'
import CollectionSupplementOptions from '../../../../collection-supplement/CollectionSupplementOptions.vue'
import { useCollectionSupplement } from '../../../../collection-supplement/useCollectionSupplement'
const props = defineProps<{ isAdministrator?: boolean; modelValue: boolean; contentIds: string[] }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]; created: [result: CollectionRunCreatedResponse]
}>()
const validSelection = computed(() => props.contentIds.length > 0 && props.contentIds.length <= 1000)
const active = computed(() => props.isAdministrator === true && props.modelValue)
const targets = computed<CollectionSupplementTargetSelection | null>(() => validSelection.value
  ? { kind: 'selected', content_ids: props.contentIds } : null)
const state = useCollectionSupplement(active, targets)
/** 显式角色门禁同时保护 UI 事件和 composable 的预检入口。 */
async function create(): Promise<void> {
  if (!props.isAdministrator) return
  const result = await state.create()
  if (result) emit('created', result)
}
</script>
<template>
  <AimaModalContainer
    v-if="isAdministrator"
    :model-value="modelValue"
    label="评论补采"
    width="840px"
    height="800px"
    :close-disabled="state.creating"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <header>
        <strong>评论补采 · {{ contentIds.length }} 条已选内容</strong><AimaButton
          variant="text"
          size="small"
          :disabled="state.creating"
          aria-label="关闭"
          @click="emit('update:modelValue', false)"
        >
          关闭
        </AimaButton>
      </header>
    </template>
    <div class="body">
      <AimaFeedbackBanner
        v-if="!validSelection"
        tone="error"
      >
        请选择 1 至 1000 条内容后补采。
      </AimaFeedbackBanner>
      <AimaFeedbackBanner tone="info">
        只补采已选笔记的详情和评论，保留全部明确选择；身份缺口会在执行结果中说明。
      </AimaFeedbackBanner>
      <CollectionSupplementOptions :state="state" />
    </div>
    <template #footer>
      <footer>
        <AimaButton
          variant="secondary"
          size="small"
          :disabled="state.creating"
          @click="emit('update:modelValue', false)"
        >
          取消
        </AimaButton><AimaButton
          variant="primary"
          :disabled="!state.canSubmit"
          @click="create"
        >
          {{ state.creating ? '创建中…' : '创建补采任务' }}
        </AimaButton>
      </footer>
    </template>
  </AimaModalContainer>
</template>
<style scoped>
header, footer { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid var(--aima-border); }
footer { justify-content: flex-end; gap: 10px; border-top: 1px solid var(--aima-border); border-bottom: 0; }
header strong { font-size: 18px; color: var(--aima-text); }
.body { display: grid; gap: 18px; padding: 20px 24px; }
</style>
