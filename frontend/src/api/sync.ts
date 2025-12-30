/**
 * 同步 API 模块
 * 
 * 配置从环境变量读取，日志保存到数据库
 */
import apiClient from './client'

// 同步配置类型（只读，从环境变量获取）
export interface SyncConfig {
    github_repo: string
    github_branch: string
    github_token_configured: boolean
    auto_sync_enabled: boolean
    auto_sync_interval: number
}

// 同步状态类型
export interface SyncStatus {
    is_configured: boolean
    is_syncing: boolean
    last_sync_at: string | null
    last_sync_message: string
    last_sync_success: boolean
    has_local_changes: boolean
    has_remote_changes: boolean
    repo: string
    branch: string
}

// 同步结果类型
export interface SyncResult {
    success: boolean
    message: string
    direction?: string
    pushed_files: string[]
    pulled_files: string[]
    synced_at?: string
}

// 同步日志类型
export interface SyncLog {
    id: string
    direction: string
    success: boolean
    message: string
    pushed_files: string[]
    pulled_files: string[]
    repo: string
    branch: string
    synced_at: string | null
}

// 测试连接结果
export interface TestConnectionResult {
    success: boolean
    message: string
}

/**
 * 获取同步配置（从环境变量读取）
 */
export async function getSyncConfig(): Promise<SyncConfig> {
    return apiClient.get('/api/sync/config')
}

/**
 * 获取同步状态
 */
export async function getSyncStatus(): Promise<SyncStatus> {
    return apiClient.get('/api/sync/status')
}

/**
 * 获取同步历史
 */
export async function getSyncHistory(limit: number = 20): Promise<{ logs: SyncLog[], total: number }> {
    return apiClient.get('/api/sync/history', { params: { limit } })
}

/**
 * 触发同步
 */
export async function triggerSync(message?: string): Promise<SyncResult> {
    return apiClient.post('/api/sync', { message })
}

/**
 * 推送到 GitHub
 */
export async function pushToGitHub(message?: string): Promise<SyncResult> {
    return apiClient.post('/api/sync/push', { message })
}

/**
 * 从 GitHub 拉取
 */
export async function pullFromGitHub(): Promise<SyncResult> {
    return apiClient.post('/api/sync/pull')
}

/**
 * 测试 GitHub 连接
 */
export async function testConnection(): Promise<TestConnectionResult> {
    return apiClient.post('/api/sync/test')
}
