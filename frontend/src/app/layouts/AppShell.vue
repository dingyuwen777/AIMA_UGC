<script setup lang="ts">
import { computed, onMounted } from 'vue'

import NotificationInbox from '../../features/identity/NotificationInbox.vue'
import { useIdentityStore } from '../../features/identity/store'
import { TaskCenter } from '../../features/task-center'
import AimaIcon, { type AimaIconName } from '../../shared/ui/AimaIcon.vue'

withDefaults(defineProps<{ sectionTitle?: string }>(), { sectionTitle: '采集运行中心' })

// App Shell 只展示当前首版真实可达页面，未来能力不以无效菜单项占位。
const identity = useIdentityStore()

const navigation = computed<{ label: string; icon: AimaIconName; to: string }[]>(() => [
  { label: '工作台', icon: 'home', to: '/' },
  { label: '声音广场', icon: 'voice', to: '/voice-plaza' },
  { label: '采集运行中心', icon: 'runtime', to: '/collection-runtime' },
  { label: '采集策略', icon: 'strategy', to: '/collection-strategy' },
  ...(identity.isAdministrator
    ? [{ label: '管理员配置', icon: 'settings' as const, to: '/admin/configuration' }]
    : []),
])

const principalRoleLabel = computed(() => {
  if (identity.principalError) return '身份不可用'
  if (!identity.principal) return '身份加载中'
  return identity.principal.role === 'administrator' ? '管理员' : '普通用户'
})

onMounted(() => void identity.ensurePrincipal())
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          爱
        </div>
        <div>
          <strong>爱玛用户声音</strong>
          <span>智能监测与洞察平台</span>
        </div>
      </div>

      <nav aria-label="业务导航">
        <span class="nav-group-label">业务工作台</span>
        <RouterLink
          v-for="item in navigation"
          :key="item.label"
          class="nav-item"
          :to="item.to"
        >
          <span class="nav-icon"><AimaIcon
            :name="item.icon"
            :size="16"
          /></span>
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div class="breadcrumb">
          业务工作台 <span>/</span> <strong>{{ sectionTitle }}</strong>
        </div>
        <div class="account-area">
          <div
            v-if="identity.principalError"
            class="principal-error"
            role="alert"
          >
            <span>身份读取失败</span>
            <button
              type="button"
              :disabled="identity.loading"
              :title="identity.principalError"
              @click="identity.retryPrincipal()"
            >
              {{ identity.loading ? '重试中…' : '重试' }}
            </button>
          </div>
          <TaskCenter />
          <NotificationInbox />
          <div class="principal">
            <strong>{{ identity.principal?.display_name ?? (identity.principalError ? '身份不可用' : '身份加载中') }}</strong>
            <span>{{ principalRoleLabel }}</span>
          </div>
          <span
            class="avatar"
            aria-label="当前用户"
          >{{ identity.principal?.display_name?.slice(0, 1) ?? '爱' }}</span>
        </div>
      </header>
      <main class="workspace-main">
        <slot />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-width: 0;
  min-height: 100vh;
  background: #f7f8fb;
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 10;
  display: flex;
  width: var(--aima-sidebar-width);
  flex-direction: column;
  border-right: 1px solid var(--aima-border);
  background: #fff;
}

.brand {
  display: flex;
  height: 76px;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
}

.brand-mark {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 6px;
  color: #fff;
  background: linear-gradient(145deg, #ff377b, #e90050);
  box-shadow: 0 8px 18px rgb(245 0 87 / 22%);
  font-size: var(--aima-font-size-section-title);
}

.brand strong,
.brand span {
  display: block;
}

.brand strong {
  white-space: nowrap;
  font-size: var(--aima-font-size-card-title);
}

.brand span {
  margin-top: 4px;
  color: #8b93a5;
  white-space: nowrap;
  font-size: var(--aima-font-size-caption);
}

nav {
  padding: 8px 12px;
}

.nav-group-label {
  display: block;
  margin-bottom: 4px;
  color: var(--aima-text-disabled);
  font-size: var(--aima-font-size-caption);
  line-height: 16px;
}

.nav-item {
  position: relative;
  display: flex;
  height: 42px;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  padding: 0 16px;
  border-radius: 8px;
  color: #3e4658;
  text-decoration: none;
  font-size: var(--aima-font-size-card-title);
}

.nav-item.router-link-active {
  color: var(--aima-primary);
  background: var(--aima-primary-soft);
  font-weight: 600;
}

.nav-item.router-link-active::before {
  position: absolute;
  left: 0;
  width: 3px;
  height: 26px;
  border-radius: 3px;
  background: var(--aima-primary);
  content: '';
}

.nav-icon {
  width: 16px;
  color: #657087;
  font-size: 20px;
  text-align: center;
}

.router-link-active .nav-icon {
  color: var(--aima-primary);
}

.workspace {
  width: calc(100% - var(--aima-sidebar-width));
  min-width: 0;
  min-height: 100vh;
  margin-left: var(--aima-sidebar-width);
}

.topbar {
  display: flex;
  min-width: 0;
  min-height: var(--aima-topbar-height);
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 var(--aima-layout-topbar-padding-x);
  border-bottom: 1px solid var(--aima-border);
  background: rgb(255 255 255 / 88%);
}

.account-area {
  display: flex;
  min-width: 0;
  flex: none;
  align-items: center;
  gap: 10px;
}

.principal-error {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--aima-danger);
  font-size: var(--aima-font-size-caption);
}

.principal-error button {
  padding: 0;
  border: 0;
  color: var(--aima-primary);
  background: transparent;
  cursor: pointer;
  font-size: var(--aima-font-size-caption);
}

.principal-error button:disabled { cursor: wait; opacity: .6; }
.principal { display: grid; gap: 2px; text-align: right; }
.principal strong { color: var(--aima-text); font-size: var(--aima-font-size-body-small); }
.principal span { color: var(--aima-text-disabled); font-size: var(--aima-font-size-caption); }

.breadcrumb {
  min-width: 0;
  overflow: hidden;
  color: #626b7c;
  font-size: var(--aima-font-size-section-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.breadcrumb span {
  margin: 0 12px;
  color: #b0b5bf;
}

.breadcrumb strong {
  color: #1f2737;
}

.avatar {
  display: grid;
  width: 32px;
  height: 32px;
  flex: none;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--aima-primary);
  font-size: var(--aima-font-size-section-title);
}

.workspace-main {
  width: min(100%, calc(var(--aima-layout-content-max-width) + var(--aima-layout-page-padding-x) + var(--aima-layout-page-padding-x)));
  min-width: 0;
  margin: 0 auto;
  padding: var(--aima-layout-page-padding-y) var(--aima-layout-page-padding-x) 40px;
}

@media (max-width: 1279px) {
  .topbar {
    flex-wrap: wrap;
    align-content: center;
    padding-block: 8px;
  }

  .account-area {
    gap: 7px;
  }
}

@media (max-width: 1080px) {
  .principal {
    display: none;
  }
}

@media (max-width: 960px) {
  .app-shell {
    --aima-sidebar-width: 160px;
  }

  .brand span,
  .breadcrumb {
    display: none;
  }

  .nav-item {
    padding-inline: 12px;
  }
}
</style>
