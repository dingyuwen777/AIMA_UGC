<script setup lang="ts">
import { ref } from 'vue'

import type { KeywordPackResponse, KeywordPackSummaryResponse } from '../../../../../generated/api/client'

defineProps<{
  packs: KeywordPackSummaryResponse[]
  selected: KeywordPackResponse | null
  loading: boolean
  saving: boolean
  toggleReason: (pack: KeywordPackSummaryResponse) => string | null
}>()

const emit = defineEmits<{
  open: [packId: string]
  toggle: [pack: KeywordPackSummaryResponse]
  addKeyword: [packId: string, text: string]
}>()

const keyword = ref('')
</script>

<template>
  <section class="panel-grid">
    <div class="table-card">
      <div class="table-head">
        <strong>Discovery 关键词包</strong><span>共 {{ packs.length }} 个</span>
      </div>
      <div v-if="loading" class="state">正在读取关键词包…</div>
      <div v-else-if="packs.length === 0" class="state">暂无 Discovery 词包，请先新建词包。</div>
      <div
        v-for="pack in packs"
        v-else
        :key="pack.id"
        class="pack-row"
        :class="{ active: selected?.id === pack.id }"
        role="button"
        tabindex="0"
        @click="emit('open', pack.id)"
        @keydown.enter="emit('open', pack.id)"
      >
        <span><strong>{{ pack.name }}</strong><small>{{ pack.description || '暂无描述' }}</small></span>
        <span class="count">{{ pack.keyword_count }} 词</span><span>v{{ pack.version }}</span>
        <span :class="['status', pack.enabled ? 'enabled' : 'disabled']">{{ pack.enabled ? '已启用' : '已停用' }}</span>
        <button
          type="button"
          class="link-button"
          :disabled="saving || !!toggleReason(pack)"
          :title="toggleReason(pack) || undefined"
          @click.stop="emit('toggle', pack)"
        >
          {{ pack.enabled ? '停用' : '启用' }}
        </button>
      </div>
    </div>

    <aside class="detail-card">
      <template v-if="selected">
        <div class="detail-title">
          <div><span>词包详情</span><strong>{{ selected.name }}</strong></div><span class="version">v{{ selected.version }}</span>
        </div>
        <p>{{ selected.description || '暂无描述' }}</p>
        <div class="keyword-list">
          <span v-for="item in selected.keywords" :key="`${item.id}-${item.platform}`">{{ item.text }}<small>{{ item.platform === 'all' ? '全部平台' : item.platform }}</small></span>
          <em v-if="selected.keywords.length === 0">当前词包还没有关键词。</em>
        </div>
        <form @submit.prevent="emit('addKeyword', selected.id, keyword.trim()); keyword = ''">
          <input v-model="keyword" maxlength="500" placeholder="新增关键词" required><button type="submit" :disabled="saving || !keyword.trim()">添加</button>
        </form>
      </template>
      <div v-else class="state">选择左侧词包查看关键词明细。</div>
    </aside>
  </section>
</template>

<style scoped>
.panel-grid { display: grid; grid-template-columns: minmax(680px, 1fr) 340px; gap: 16px; }
.table-card,.detail-card { border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.table-head { display: flex; height: 54px; align-items: center; justify-content: space-between; padding: 0 18px; border-bottom: 1px solid var(--aima-border); }
.table-head span,.detail-card p { color: #758094; font-size: 13px; }
.pack-row { display: grid; width: 100%; grid-template-columns: 1fr 72px 50px 72px 48px; align-items: center; gap: 10px; padding: 15px 18px; border: 0; border-bottom: 1px solid #edf0f4; color: #4e596d; background: #fff; text-align: left; cursor: pointer; }
.pack-row.active { background: #fff7fa; box-shadow: inset 3px 0 var(--aima-primary); }
.pack-row strong,.pack-row small { display: block; }.pack-row strong { color: #1e2838; }.pack-row small { margin-top: 5px; color: #818b9d; }
.status { width: max-content; padding: 4px 8px; border-radius: 5px; font-size: 12px; }.enabled { color: #118852; background: #eaf8f1; }.disabled { color: #687386; background: #eef1f5; }
.link-button { border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; }.link-button:disabled { color: #98a1b1; cursor: not-allowed; opacity: .75; }
.detail-card { padding: 18px; }.detail-title { display: flex; justify-content: space-between; }.detail-title span,.detail-title strong { display: block; }.detail-title span { color: #7b8598; font-size: 12px; }.detail-title strong { margin-top: 5px; font-size: 18px; }.version { color: var(--aima-primary) !important; }
.keyword-list { display: flex; max-height: 330px; flex-wrap: wrap; gap: 8px; overflow: auto; margin: 18px 0; }.keyword-list > span { padding: 7px 9px; border: 1px solid #dce4f0; border-radius: 6px; color: #344258; background: #f8faff; font-size: 13px; }.keyword-list small { margin-left: 5px; color: #8993a3; }.keyword-list em { color: #929aaa; font-style: normal; }
form { display: flex; gap: 8px; }input { min-width: 0; height: 38px; flex: 1; padding: 0 10px; border: 1px solid #dce1e9; border-radius: 6px; }form button { width: 62px; border: 0; border-radius: 6px; color: #fff; background: var(--aima-primary); cursor: pointer; }
.state { display: grid; min-height: 190px; place-items: center; color: #8a93a3; }
</style>