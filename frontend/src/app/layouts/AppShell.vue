<script setup lang="ts">
import { computed, onMounted } from 'vue'

import NotificationInbox from '../../features/identity/NotificationInbox.vue'
import { useIdentityStore } from '../../features/identity/store'
import AimaIcon, { type AimaIconName } from '../../shared/ui/AimaIcon.vue'

withDefaults(defineProps<{ sectionTitle?: string }>(), { sectionTitle: '采集运行中心' })

// App Shell 只展示当前首版真实可达页面，未来能力不以无效菜单项占位。
const identity = useIdentityStore()

const navigation = computed<{ label: string; icon: AimaIconName; to: string }[]>(() => [
  { label: '首页', icon: 'home', to: '/' },
  { label: '声音广场', icon: 'voice', to: '/voice-plaza' },
  { label: '采集运行中心', icon: 'runtime', to: '/collection-runtime' },
  { label: '采集策略', icon: 'strategy', to: '/collection-strategy' },
  ...(identity.isAdministrator
    ? [{ label: '管理员配置', icon: 'settings' as const, to: '/admin/configuration' }]
    : []),
])

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
          <NotificationInbox />
          <div class="principal">
            <strong>{{ identity.principal?.display_name ?? '身份加载中' }}</strong>
            <span>{{ identity.principal?.role === 'administrator' ? '管理员' : '普通用户' }}</span>
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
  min-width: 1180px;
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
  font-size: 16px;
}

.brand strong,
.brand span {
  display: block;
}

.brand strong {
  white-space: nowrap;
  font-size: 14px;
}

.brand span {
  margin-top: 4px;
  color: #8b93a5;
  white-space: nowrap;
  font-size: 11px;
}

nav {
  padding: 8px 12px;
}

.nav-group-label {
  display: block;
  margin-bottom: 4px;
  color: var(--aima-text-disabled);
  font-size: 11px;
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
  font-size: 14px;
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
  min-height: 100vh;
  margin-left: var(--aima-sidebar-width);
}

.topbar {
  display: flex;
  height: var(--aima-topbar-height);
  align-items: center;
  justify-content: space-between;
  padding: 0 26px;
  border-bottom: 1px solid var(--aima-border);
  background: rgb(255 255 255 / 88%);
}

.account-area { display: flex; align-items: center; gap: 10px; }
.principal { display: grid; gap: 2px; text-align: right; }
.principal strong { color: var(--aima-text); font-size: 11px; }
.principal span { color: var(--aima-text-disabled); font-size: 9px; }

.breadcrumb {
  color: #626b7c;
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
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--aima-primary);
  font-size: 15px;
}

.workspace-main {
  padding: 24px 24px 40px;
}
</style>
