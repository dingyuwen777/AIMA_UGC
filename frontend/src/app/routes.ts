import type { RouteRecordRaw } from 'vue-router'

import HomeView from '../views/HomeView.vue'
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
