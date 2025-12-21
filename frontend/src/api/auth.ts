import apiClient from './client'

export type LoginRequest = {
    username: string
    password: string
}

export type LoginResponse = {
    access_token: string
    token_type: string
}

export type UserResponse = {
    id: number
    username: string
    email?: string
    created_at: string
}

export const authApi = {
    // 登录
    login(data: LoginRequest): Promise<LoginResponse> {
        return apiClient.post('/api/auth/login', data)
    },

    // 刷新 Token
    refresh(): Promise<LoginResponse> {
        return apiClient.post('/api/auth/refresh')
    },

    // 获取当前用户信息
    getCurrentUser(): Promise<UserResponse> {
        return apiClient.get('/api/auth/me')
    }
}
