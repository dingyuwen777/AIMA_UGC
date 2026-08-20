import type { RouteRecordRaw } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import CollectionRuntimePage from '../features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/collection-runtime',
    name: 'collection-runtime',
    component: CollectionRuntimePage,
  },
]
