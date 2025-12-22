import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Framework7 from 'framework7/bundle'
import Framework7Vue from 'framework7-vue'
import 'framework7/css/bundle'
import 'framework7-icons/css/framework7-icons.css'
import App from './App.vue'
import router from './router'
import './style.css'

// Initialise Framework7
Framework7.use(Framework7Vue)

// 创建 Vue 应用
const app = createApp(App)

// 使用 Pinia 状态管理
app.use(createPinia())

// 使用 Vue Router
app.use(router)

// 挂载应用
app.mount('#app')
