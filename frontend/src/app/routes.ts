import type { RouteRecordRaw } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import NoAccessView from '../views/NoAccessView.vue'
import CollectionRuntimePage from '../features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue'
import CollectionStrategyPage from '../features/collection-strategy/pages/CollectionStrategyPage/CollectionStrategyPage.vue'
import VoicePlazaPage from '../features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue'
import AdminConfigurationPage from '../features/admin-configuration/pages/AdminConfigurationPage.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    // 未登录（后端 401）时守卫改道到这里；本页展示飞书登录入口。
    path: '/login',
    name: 'login',
    component: LoginView,
  },
  {
    // 已登录但无权限（后端 403）时改道到这里，**刻意不再提供"重新登录"**：
    // 再登录一次结果仍是 403，只会形成死循环。
    path: '/no-access',
    name: 'no-access',
    component: NoAccessView,
  },
  {
    path: '/voice-plaza',
    name: 'voice-plaza',
    component: VoicePlazaPage,
  },
  {
    path: '/collection-runtime',
    name: 'collection-runtime',
    component: CollectionRuntimePage,
  },
  {
    path: '/collection-strategy',
    name: 'collection-strategy',
    component: CollectionStrategyPage,
  },
  {
    path: '/admin/configuration',
    name: 'admin-configuration',
    component: AdminConfigurationPage,
    meta: { requiresAdministrator: true },
  },
]
