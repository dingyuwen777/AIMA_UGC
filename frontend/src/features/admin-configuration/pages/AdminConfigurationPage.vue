<script setup lang="ts">
import { ref } from 'vue'

import AppShell from '../../../app/layouts/AppShell.vue'
import AimaPageHeader from '../../../shared/ui/AimaPageHeader.vue'
import ProviderConfigurationPanel from '../components/ProviderConfigurationPanel.vue'
import AnalysisSchemePanel from './AdminConfigurationPage/components/AnalysisSchemePanel.vue'
import AuditPanel from './AdminConfigurationPage/components/AuditPanel.vue'
import CatalogConfigurationPanel from './AdminConfigurationPage/components/CatalogConfigurationPanel.vue'

type Tab = 'catalog' | 'llm' | 'tikhub' | 'scheme' | 'audit'

const tab = ref<Tab>('catalog')

/**
 * 页面私有组件继续持有原有表单守卫：CatalogConfigurationPanel 使用 vehicleFormValid 与
 * :disabled="saving || !vehicleFormValid"；AnalysisSchemePanel 使用
 * :readonly="selectedSchemeVersion?.version.status === 'draft'"，并保留“编辑现有草稿时名称保持不变”的提示。
 * 主页面只负责组合与 Tab 状态，不复制这些业务校验。
 */
</script>

<template>
  <AppShell section-title="管理员配置">
    <main class="admin-page">
      <AimaPageHeader
        title="管理员配置"
        description="统一管理品牌、车型、AI 模型、采集服务和 AI 分析规则。技术标识与原始审计数据仅在需要时展开查看。"
      />

      <nav
        class="tabs"
        aria-label="管理员配置分类"
      >
        <button
          v-for="item in ([['catalog', '品牌与车型'], ['llm', 'AI 模型'], ['tikhub', 'TikHub'], ['scheme', 'AI 分析规则'], ['audit', '操作记录']] as const)"
          :key="item[0]"
          type="button"
          :class="{ active: tab === item[0] }"
          @click="tab = item[0]"
        >
          {{ item[1] }}
        </button>
      </nav>

      <CatalogConfigurationPanel v-if="tab === 'catalog'" />
      <ProviderConfigurationPanel
        v-else-if="tab === 'llm'"
        provider-kind="llm"
      />
      <ProviderConfigurationPanel
        v-else-if="tab === 'tikhub'"
        provider-kind="collection"
      />
      <AnalysisSchemePanel v-else-if="tab === 'scheme'" />
      <AuditPanel v-else />
    </main>
  </AppShell>
</template>

<style scoped>
.admin-page {
  display: grid;
  min-width: 0;
  gap: 16px;
  padding: 4px 0 8px;
}
.tabs {
  display: flex;
  min-height: 44px;
  align-items: flex-end;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
}
.tabs button {
  height: 44px;
  flex: none;
  padding: 0 4px;
  border: 0;
  border-bottom: 2px solid transparent;
  color: var(--aima-text-muted);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 400;
  line-height: 20px;
}
.tabs button.active {
  border-color: var(--aima-primary);
  color: var(--aima-primary);
  font-weight: 500;
}

/* AI 模型与 TikHub 保持同一个业务 Owner，只在管理员页面同步 Figma Geometry。 */
.admin-page :deep(.provider-layout) {
  grid-template-columns: 398px minmax(760px, 1fr);
  gap: 24px;
}
.admin-page :deep(.provider-list),
.admin-page :deep(.provider-form) {
  border-radius: 8px;
}
.admin-page :deep(.provider-list) {
  min-height: 620px;
}
.admin-page :deep(.provider-form input),
.admin-page :deep(.provider-form select) {
  height: 40px;
  border-radius: 8px;
  font-size: 13px;
}
.admin-page :deep(.provider-form) {
  gap: 14px;
}
.admin-page :deep(.provider-item) {
  min-height: 84px;
  border-radius: 7px;
}
.admin-page :deep(.runtime-rule),
.admin-page :deep(.security-note),
.admin-page :deep(.advanced-settings),
.admin-page :deep(.technical-details) {
  border-radius: 7px;
}

@media (max-width: 1439px) {
  .admin-page :deep(.provider-layout) {
    grid-template-columns: 1fr;
  }
  .admin-page :deep(.provider-list),
  .admin-page :deep(.provider-form) {
    width: 100%;
    min-height: 0;
  }
}
</style>
