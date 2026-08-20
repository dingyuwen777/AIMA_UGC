import type { RouteRecordRaw } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import CollectionRuntimePage from '../features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue'
import VoicePlazaPage from '../features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue'

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
]
