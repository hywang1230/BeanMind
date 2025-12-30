<template>
    <f7-page name="sync">
        <f7-navbar title="同步与备份">
            <template #left>
                <f7-link @click="goBack">
                    <f7-icon f7="chevron_left"></f7-icon>
                </f7-link>
            </template>
        </f7-navbar>

        <!-- 同步状态卡片 -->
        <f7-card class="sync-status-card">
            <f7-card-header>
                <div class="status-header">
                    <f7-icon :ios="status.is_configured ? 'f7:cloud_fill' : 'f7:cloud'"
                        :md="status.is_configured ? 'material:cloud_done' : 'material:cloud_off'"
                        :color="status.is_configured ? 'blue' : 'gray'"></f7-icon>
                    <span>GitHub 同步</span>
                </div>
                <f7-badge v-if="status.is_configured" color="green">已配置</f7-badge>
                <f7-badge v-else color="gray">未配置</f7-badge>
            </f7-card-header>
            <f7-card-content>
                <div v-if="status.is_configured" class="status-info">
                    <div class="info-row">
                        <span class="label">仓库</span>
                        <span class="value">{{ status.repo }}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">分支</span>
                        <span class="value">{{ status.branch }}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">上次同步</span>
                        <span class="value">{{ formatLastSync(status.last_sync_at) }}</span>
                    </div>
                    <div v-if="status.last_sync_message" class="info-row">
                        <span class="label">同步消息</span>
                        <span class="value" :class="{ 'text-color-red': !status.last_sync_success }">
                            {{ status.last_sync_message }}
                        </span>
                    </div>
                </div>
                <div v-else class="status-empty">
                    <p>请配置环境变量以启用 GitHub 同步：</p>
                    <ul class="env-hints">
                        <li><code>GITHUB_TOKEN</code> - GitHub Personal Access Token</li>
                        <li><code>GITHUB_REPO</code> - 仓库名 (username/repo)</li>
                        <li><code>GITHUB_BRANCH</code> - 分支名 (默认 main)</li>
                    </ul>
                </div>
            </f7-card-content>
            <f7-card-footer v-if="status.is_configured">
                <f7-button fill :loading="syncing" :disabled="syncing" @click="handleSync">
                    <f7-icon ios="f7:arrow_2_circlepath" md="material:sync"></f7-icon>
                    {{ syncing ? '同步中...' : '立即同步' }}
                </f7-button>
            </f7-card-footer>
        </f7-card>

        <!-- 配置信息展示 -->
        <f7-block-title v-if="status.is_configured">当前配置</f7-block-title>
        <f7-list v-if="status.is_configured" inset strong>
            <f7-list-item title="仓库" :after="config.github_repo || '未配置'"></f7-list-item>
            <f7-list-item title="分支" :after="config.github_branch"></f7-list-item>
            <f7-list-item title="Token" :after="config.github_token_configured ? '已配置' : '未配置'"></f7-list-item>
            <f7-list-item title="自动同步" :after="config.auto_sync_enabled ? '已启用' : '未启用'"></f7-list-item>
        </f7-list>

        <!-- 操作按钮 -->
        <f7-block v-if="status.is_configured">
            <f7-button outline :loading="testing" :disabled="testing" @click="handleTestConnection">
                测试连接
            </f7-button>
        </f7-block>

        <!-- 同步历史 -->
        <f7-block-title>同步历史</f7-block-title>
        <f7-list v-if="history.length > 0" inset strong media-list>
            <f7-list-item v-for="log in history" :key="log.id" :title="getDirectionText(log.direction)"
                :subtitle="log.message" :after="formatSyncTime(log.synced_at)">
                <template #media>
                    <f7-icon :ios="log.success ? 'f7:checkmark_circle_fill' : 'f7:xmark_circle_fill'"
                        :md="log.success ? 'material:check_circle' : 'material:cancel'"
                        :color="log.success ? 'green' : 'red'"></f7-icon>
                </template>
            </f7-list-item>
        </f7-list>
        <f7-block v-else class="text-align-center">
            <p class="text-color-gray">暂无同步记录</p>
        </f7-block>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { f7 } from 'framework7-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

function goBack() {
    router.back()
}

import {
    getSyncConfig,
    getSyncStatus,
    getSyncHistory,
    triggerSync,
    testConnection,
    type SyncConfig,
    type SyncStatus,
    type SyncLog
} from '../../api/sync'

// 状态
const status = reactive<SyncStatus>({
    is_configured: false,
    is_syncing: false,
    last_sync_at: null,
    last_sync_message: '',
    last_sync_success: true,
    has_local_changes: false,
    has_remote_changes: false,
    repo: '',
    branch: 'main'
})

const config = reactive<SyncConfig>({
    github_repo: '',
    github_branch: 'main',
    github_token_configured: false,
    auto_sync_enabled: false,
    auto_sync_interval: 300
})

const history = ref<SyncLog[]>([])
const syncing = ref(false)
const testing = ref(false)

// 加载数据
async function loadData() {
    try {
        const [configData, statusData, historyData] = await Promise.all([
            getSyncConfig(),
            getSyncStatus(),
            getSyncHistory(10)
        ])
        Object.assign(config, configData)
        Object.assign(status, statusData)
        history.value = historyData.logs
    } catch (error: any) {
        f7.toast.create({
            text: '加载数据失败: ' + (error.message || '未知错误'),
            closeTimeout: 2000
        }).open()
    }
}

// 测试连接
async function handleTestConnection() {
    testing.value = true
    try {
        const result = await testConnection()
        if (result.success) {
            f7.toast.create({
                text: '✓ 连接成功',
                closeTimeout: 2000
            }).open()
        } else {
            f7.dialog.alert(result.message, '连接失败')
        }
    } catch (error: any) {
        f7.dialog.alert(error.message || '测试失败', '错误')
    } finally {
        testing.value = false
    }
}

// 触发同步
async function handleSync() {
    syncing.value = true
    try {
        const result = await triggerSync()
        if (result.success) {
            f7.toast.create({
                text: '✓ ' + result.message,
                closeTimeout: 3000
            }).open()
            // 刷新数据
            await loadData()
        } else {
            f7.dialog.alert(result.message, '同步失败')
        }
    } catch (error: any) {
        f7.dialog.alert(error.message || '同步失败', '错误')
    } finally {
        syncing.value = false
    }
}

// 格式化时间
function formatLastSync(dateStr: string | null): string {
    if (!dateStr) return '从未同步'
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
    return date.toLocaleDateString()
}

function formatSyncTime(dateStr: string | null): string {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    return date.toLocaleString()
}

function getDirectionText(direction: string): string {
    const map: Record<string, string> = {
        'push': '推送',
        'pull': '拉取',
        'both': '同步'
    }
    return map[direction] || direction
}

onMounted(() => {
    loadData()
})
</script>

<style scoped>
.sync-status-card {
    margin-top: 16px;
}

.sync-status-card .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.status-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
}

.status-info {
    padding: 8px 0;
}

.info-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid var(--f7-list-item-border-color);
}

.info-row:last-child {
    border-bottom: none;
}

.info-row .label {
    color: var(--f7-label-text-color);
}

.info-row .value {
    color: var(--f7-text-color);
    font-weight: 500;
}

.status-empty {
    text-align: left;
    color: var(--f7-label-text-color);
    padding: 8px 0;
}

.status-empty p {
    margin-bottom: 8px;
}

.env-hints {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
}

.env-hints li {
    margin-bottom: 4px;
}

.env-hints code {
    background: var(--f7-input-bg-color);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
}

.sync-status-card .card-footer {
    padding: 12px 16px;
}

.sync-status-card .card-footer .button {
    width: 100%;
}
</style>
