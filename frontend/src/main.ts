import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Framework7 from 'framework7/bundle'
import Framework7Vue, { registerComponents } from 'framework7-vue/bundle'
import 'framework7/css/bundle'
import 'framework7-icons/css/framework7-icons.css'
import App from './App.vue'
import router from './router'
import './style.css'

// Initialise Framework7
Framework7.use(Framework7Vue)

// 创建 Vue 应用
const app = createApp(App)

// 注册 Framework7 Vue 组件
registerComponents(app)

// 使用 Pinia 状态管理
app.use(createPinia())

// 使用 Vue Router
app.use(router)

// 挂载应用
app.mount('#app')
