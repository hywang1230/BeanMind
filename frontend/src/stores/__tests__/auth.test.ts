import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock API
vi.mock('../api/auth', () => ({
    authApi: {
        login: vi.fn(),
        refresh: vi.fn(),
        getCurrentUser: vi.fn(),
    }
}))

describe('AuthStore', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        localStorage.clear()
    })

    it('初始状态应该未认证', () => {
        const store = useAuthStore()
        expect(store.isAuthenticated).toBe(false)
        expect(store.token).toBe(null)
        expect(store.user).toBe(null)
    })

    it('从 localStorage 读取 token', () => {
        localStorage.setItem('token', 'test-token')
        const store = useAuthStore()
        expect(store.token).toBe('test-token')
    })

    it('登出应该清除 token 和用户信息', () => {
        const store = useAuthStore()
        store.token = 'test-token'
        store.user = { id: 1, username: 'test', created_at: '2024-01-01' }

        store.logout()

        expect(store.token).toBe(null)
        expect(store.user).toBe(null)
        expect(localStorage.getItem('token')).toBe(null)
    })
})
