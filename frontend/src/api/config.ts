import apiClient from './client'

export interface AppConfig {
    auth_mode: 'none' | 'single_user' | 'multi_user'
    ai_enabled: boolean
    backup_provider: string
}

export const configApi = {
    async getConfig(): Promise<AppConfig> {
        // apiClient 响应拦截器已经返回 response.data，所以这里直接返回即可
        return apiClient.get<AppConfig>('/api/config') as any as AppConfig
    }
}
