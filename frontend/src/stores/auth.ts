import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginRequest, type UserResponse } from '../api/auth'
import { configApi } from '../api/config'

export const useAuthStore = defineStore('auth', () => {
    // 状态
    const token = ref<string | null>(localStorage.getItem('token'))
    const user = ref<UserResponse | null>(null)
    const authMode = ref<'none' | 'single_user' | 'multi_user'>('single_user')
    const configLoaded = ref(false)

    // 计算属性
    const isAuthenticated = computed(() => {
        // 如果是 none 模式，总是认为已认证
        if (authMode.value === 'none') {
            return true
        }
        return !!token.value
    })

    const requiresAuth = computed(() => authMode.value !== 'none')

    // 操作
    async function login(credentials: LoginRequest) {
        try {
            const response = await authApi.login(credentials)
            token.value = response.access_token
            localStorage.setItem('token', response.access_token)

            // 获取用户信息
            await fetchCurrentUser()

            return true
        } catch (error) {
            console.error('Login failed:', error)
            throw error
        }
    }

    async function fetchCurrentUser() {
        try {
            user.value = await authApi.getCurrentUser()
        } catch (error) {
            console.error('Failed to fetch user:', error)
            logout()
        }
    }

    function logout() {
        token.value = null
        user.value = null
        localStorage.removeItem('token')
    }

    async function refreshToken() {
        try {
            const response = await authApi.refresh()
            token.value = response.access_token
            localStorage.setItem('token', response.access_token)
        } catch (error) {
            logout()
            throw error
        }
    }

    async function fetchConfig() {
        try {
            const config = await configApi.getConfig()
            // 验证配置数据的完整性
            if (config && config.auth_mode) {
                authMode.value = config.auth_mode
            } else {
                console.warn('Config data is incomplete, using default auth mode')
                authMode.value = 'single_user'
            }
            configLoaded.value = true
        } catch (error) {
            console.error('Failed to fetch config:', error)
            // 默认使用 single_user 模式
            authMode.value = 'single_user'
            configLoaded.value = true
        }
    }

    // 初始化时检查 token 和配置
    fetchConfig()
    if (token.value) {
        fetchCurrentUser()
    }

    return {
        token,
        user,
        authMode,
        configLoaded,
        requiresAuth,
        isAuthenticated,
        login,
        logout,
        refreshToken,
        fetchCurrentUser,
        fetchConfig
    }
})
