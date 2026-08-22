<script setup lang="ts">
withDefaults(defineProps<{ sectionTitle?: string }>(), { sectionTitle: '采集运行中心' })

// App Shell 只展示当前首版真实可达页面，未来能力不以无效菜单项占位。
const navigation = [
  { label: '首页', icon: '⌂', to: '/' },
  { label: '声音广场', icon: '◌', to: '/voice-plaza' },
  { label: '采集运行中心', icon: '▣', to: '/collection-runtime' },
  { label: '采集策略', icon: '◎', to: '/collection-strategy' },
]
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
          <span>智能舆情与洞察平台</span>
        </div>
      </div>

      <nav aria-label="业务导航">
        <RouterLink
          v-for="item in navigation"
          :key="item.label"
          class="nav-item"
          :to="item.to"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div class="breadcrumb">
          业务工作台 <span>/</span> <strong>{{ sectionTitle }}</strong>
        </div>
        <div
          class="topbar-actions"
          aria-hidden="true"
        >
          <span>♧</span><span>⚙</span><span class="avatar">爱</span>
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
  width: 232px;
  flex-direction: column;
  border-right: 1px solid var(--aima-border);
  background: #fff;
}

.brand {
  display: flex;
  height: 82px;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  border-bottom: 1px solid var(--aima-border);
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 11px;
  color: #fff;
  background: linear-gradient(145deg, #ff377b, #e90050);
  box-shadow: 0 8px 18px rgb(245 0 87 / 22%);
  font-size: 24px;
}

.brand strong,
.brand span {
  display: block;
}

.brand strong {
  font-size: 16px;
}

.brand span {
  margin-top: 4px;
  color: #8b93a5;
  font-size: 11px;
}

nav {
  padding: 22px 12px;
}

.nav-item {
  position: relative;
  display: flex;
  height: 46px;
  align-items: center;
  gap: 13px;
  margin-bottom: 4px;
  padding: 0 15px;
  border-radius: 8px;
  color: #3e4658;
  text-decoration: none;
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
  width: 20px;
  color: #657087;
  font-size: 20px;
  text-align: center;
}

.router-link-active .nav-icon {
  color: var(--aima-primary);
}

.workspace {
  width: calc(100% - 232px);
  min-height: 100vh;
  margin-left: 232px;
}

.topbar {
  display: flex;
  height: 60px;
  align-items: center;
  justify-content: space-between;
  padding: 0 26px;
  border-bottom: 1px solid var(--aima-border);
  background: rgb(255 255 255 / 88%);
}

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

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 22px;
  font-size: 20px;
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
  padding: 28px 24px 40px;
}
</style>
