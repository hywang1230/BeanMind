import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
    aiApi,
    type AISkill,
    type ChatMessage,
    type ChatContext,
    type ChatSessionSummary,
    type QuickQuestion,
    type StreamEvent,
} from '../api/ai'

type PendingInterrupt = Extract<StreamEvent, { type: 'interrupt' }>

// 生成 UUID（使用浏览器内置 API，带 fallback）
function generateId(): string {
    // 优先使用原生 API
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID()
    }

    // Fallback: 生成符合 UUID v4 格式的字符串
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
    })
}

export const useAIStore = defineStore('ai', () => {
    // 状态
    const messages = ref<ChatMessage[]>([])
    const sessionId = ref<string>('')
    const isLoading = ref(false)
    const quickQuestions = ref<QuickQuestion[]>([])
    const skills = ref<AISkill[]>([])
    const sessions = ref<ChatSessionSummary[]>([])
    const pendingInterrupt = ref<PendingInterrupt | null>(null)
    const statusText = ref('')
    const error = ref<string | null>(null)

    // 计算属性
    const hasMessages = computed(() => messages.value.length > 0)
    const lastMessage = computed(() => messages.value[messages.value.length - 1])

    // 初始化会话
    function initSession() {
        if (!sessionId.value) {
            sessionId.value = generateId()
        }
    }

    // 获取快捷问题
    async function fetchQuickQuestions() {
        try {
            const response = await aiApi.getQuickQuestions()
            quickQuestions.value = response.questions
        } catch (e) {
            console.error('获取快捷问题失败:', e)
            // 使用默认问题
            quickQuestions.value = [
                { id: 'q1', text: '本月支出分析', icon: 'chart_pie' },
                { id: 'q2', text: '最近消费趋势', icon: 'graph_square' },
                { id: 'q3', text: '上月账单总结', icon: 'doc_text' },
                { id: 'q4', text: '今日消费情况', icon: 'calendar' },
            ]
        }
    }

    async function fetchSkills() {
        try {
            const response = await aiApi.getSkills()
            skills.value = response.skills
        } catch (e) {
            console.error('获取技能列表失败:', e)
            skills.value = []
        }
    }

    // 获取会话列表
    async function fetchSessions() {
        try {
            const response = await aiApi.listSessions()
            sessions.value = response.sessions
        } catch (e) {
            console.error('获取会话列表失败:', e)
        }
    }

    // 发送消息
    async function sendMessage(content: string, context?: ChatContext) {
        if (!content.trim() || isLoading.value) return

        initSession()
        error.value = null
        pendingInterrupt.value = null
        statusText.value = ''
        isLoading.value = true

        // 添加用户消息
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: content.trim(),
            created_at: new Date().toISOString(),
        }
        messages.value.push(userMessage)

        // 构建历史
        const history = messages.value
            .slice(0, -1)  // 排除刚添加的用户消息
            .map(m => ({ role: m.role, content: m.content }))

        try {
            // 发起请求
            const response = await aiApi.chat({
                message: content.trim(),
                session_id: sessionId.value,
                history,
                context: context || {
                    source_page: '/ai',
                },
            })

            // 更新 session_id
            if (response.session_id) {
                sessionId.value = response.session_id
            }

            // 添加 AI 回复消息
            messages.value.push(response.message)
            await fetchSessions()

        } catch (e) {
            const errorMsg = e instanceof Error ? e.message : '请求失败'
            error.value = errorMsg

            // 添加错误消息
            const errorMessage: ChatMessage = {
                id: generateId(),
                role: 'assistant',
                content: `抱歉，处理您的请求时出现了问题：${errorMsg}`,
                created_at: new Date().toISOString(),
            }
            messages.value.push(errorMessage)
        } finally {
            isLoading.value = false
        }
    }

    // 流式发送消息
    async function sendMessageStream(content: string, context?: ChatContext) {
        if (!content.trim() || isLoading.value) return

        initSession()
        error.value = null
        pendingInterrupt.value = null
        statusText.value = ''
        isLoading.value = true

        // 添加用户消息
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: content.trim(),
            created_at: new Date().toISOString(),
        }
        messages.value.push(userMessage)

        // 延迟创建 AI 消息（在收到第一个 token 时创建）
        let tempAiMessage: ChatMessage | null = null

        // 构建历史（排除刚添加的用户消息）
        const history = messages.value
            .slice(0, -1)
            .map(m => ({ role: m.role, content: m.content }))

        try {
            await aiApi.chatStream(
                {
                    message: content.trim(),
                    session_id: sessionId.value,
                    history,
                    context: context || {
                        source_page: '/ai',
                    },
                },
                // onToken: 实时更新消息内容
                (token: string) => {
                    // 如果是第一个 token，创建 AI 消息
                    if (!tempAiMessage) {
                        tempAiMessage = {
                            id: generateId(),
                            role: 'assistant',
                            content: token,
                            created_at: new Date().toISOString(),
                        }
                        messages.value.push(tempAiMessage)
                    } else {
                        // 追加 token 并触发响应式更新
                        tempAiMessage.content += token
                        const index = messages.value.findIndex(m => m.id === tempAiMessage!.id)
                        if (index !== -1) {
                            messages.value[index] = { ...tempAiMessage }
                        }
                    }
                },
                // onDone: 完成时更新为完整消息
                (message: ChatMessage) => {
                    if (tempAiMessage) {
                        const index = messages.value.findIndex(m => m.id === tempAiMessage!.id)
                        if (index !== -1) {
                            messages.value[index] = message
                        }
                    }
                },
                // onError: 处理错误
                (errorMsg: string) => {
                    error.value = errorMsg
                    // 如果还没创建消息，则创建一个错误消息
                    if (!tempAiMessage) {
                        tempAiMessage = {
                            id: generateId(),
                            role: 'assistant',
                            content: `抱歉，处理您的请求时出现了问题：${errorMsg}`,
                            created_at: new Date().toISOString(),
                        }
                        messages.value.push(tempAiMessage)
                    } else {
                        tempAiMessage.content = `抱歉，处理您的请求时出现了问题：${errorMsg}`
                        const index = messages.value.findIndex(m => m.id === tempAiMessage!.id)
                        if (index !== -1) {
                            messages.value[index] = { ...tempAiMessage }
                        }
                    }
                },
                (event: StreamEvent) => {
                    switch (event.type) {
                        case 'session':
                            sessionId.value = event.session_id
                            break
                        case 'interrupt':
                            pendingInterrupt.value = event
                            statusText.value = event.missing_fields?.length
                                ? `待补充字段：${event.missing_fields.join('、')}`
                                : '待确认草稿'
                            fetchSessions().catch(console.error)
                            break
                        case 'progress':
                            statusText.value = event.content || event.step || '处理中'
                            break
                        case 'skill':
                            statusText.value = `已选择能力：${event.skill_id}`
                            break
                        case 'agent':
                            statusText.value = `当前代理：${event.agent_id}`
                            break
                        case 'done':
                            if (!pendingInterrupt.value) {
                                statusText.value = ''
                            }
                            fetchSessions().catch(console.error)
                            break
                        case 'error':
                            statusText.value = ''
                            break
                        default:
                            break
                    }
                },
            )
        } catch {
            // 错误已在 onError 回调中处理
        } finally {
            isLoading.value = false
        }
    }

    // 清空消息
    function clearMessages() {
        messages.value = []
        error.value = null
        pendingInterrupt.value = null
        statusText.value = ''

        // 如果有会话，清空服务端会话
        if (sessionId.value) {
            aiApi.clearSession(sessionId.value).catch(console.error)
        }
    }

    // 新建对话
    function newConversation() {
        // 直接清空本地状态，不调用服务端
        messages.value = []
        error.value = null
        pendingInterrupt.value = null
        statusText.value = ''
        sessionId.value = generateId()
    }

    // 加载会话历史
    async function loadSessionHistory(sid: string) {
        isLoading.value = true
        try {
            const session = await aiApi.getSessionHistory(sid)
            sessionId.value = session.id
            messages.value = session.messages
            pendingInterrupt.value = session.pending_action
                ? {
                    type: 'interrupt',
                    session_id: session.id,
                    action_type: session.pending_action.action_type,
                    draft: session.pending_action.draft,
                    missing_fields: session.pending_action.missing_fields,
                    confidence: session.pending_action.confidence,
                    assumptions: session.pending_action.assumptions,
                }
                : null
            statusText.value = pendingInterrupt.value
                ? (pendingInterrupt.value.missing_fields?.length
                    ? `待补充字段：${pendingInterrupt.value.missing_fields.join('、')}`
                    : '待确认草稿')
                : ''
        } catch (e) {
            console.error('加载会话历史失败:', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    async function resumePendingAction(
        action: 'confirm' | 'cancel' | 'edit',
        draft?: Record<string, unknown>
    ) {
        if (!sessionId.value || !pendingInterrupt.value) return

        isLoading.value = true
        error.value = null
        try {
            const response = await aiApi.resumeSession(sessionId.value, { action, draft })
            messages.value.push(response.message)
            if (action === 'edit' && draft) {
                pendingInterrupt.value = {
                    ...pendingInterrupt.value,
                    draft,
                }
                statusText.value = '草稿已更新，等待确认'
            } else {
                await loadSessionHistory(sessionId.value)
            }
            await fetchSessions()
        } catch (e) {
            const errorMsg = e instanceof Error ? e.message : '处理草稿失败'
            error.value = errorMsg
            throw e
        } finally {
            isLoading.value = false
        }
    }

    async function deleteSession(sid: string) {
        await aiApi.deleteSession(sid)
        sessions.value = sessions.value.filter(session => session.id !== sid)

        if (sessionId.value === sid) {
            messages.value = []
            sessionId.value = generateId()
            pendingInterrupt.value = null
            statusText.value = ''
            error.value = null
        }
    }

    return {
        // 状态
        messages,
        sessionId,
        isLoading,
        quickQuestions,
        skills,
        sessions,
        pendingInterrupt,
        statusText,
        error,

        // 计算属性
        hasMessages,
        lastMessage,

        // 方法
        initSession,
        fetchQuickQuestions,
        fetchSkills,
        fetchSessions,
        sendMessage,
        sendMessageStream,
        resumePendingAction,
        deleteSession,
        clearMessages,
        newConversation,
        loadSessionHistory,
    }
})
