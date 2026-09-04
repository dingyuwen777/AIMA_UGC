import { createPinia } from 'pinia'
import { createApp } from 'vue'

import './shared/styles/tokens.css'
import './shared/styles/responsive.css'

import App from './App.vue'
import { router } from './app/router'

createApp(App).use(createPinia()).use(router).mount('#app')