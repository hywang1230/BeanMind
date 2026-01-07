import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { aiApi, type ChatMessage, type QuickQuestion } from '../api/ai'

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

    // 发送消息
    async function sendMessage(content: string) {
        if (!content.trim() || isLoading.value) return

        initSession()
        error.value = null
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
            })

            // 更新 session_id
            if (response.session_id) {
                sessionId.value = response.session_id
            }

            // 添加 AI 回复消息
            messages.value.push(response.message)

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
    async function sendMessageStream(content: string) {
        if (!content.trim() || isLoading.value) return

        initSession()
        error.value = null
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
                }
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
        sessionId.value = generateId()
    }

    // 加载会话历史
    async function loadSessionHistory(sid: string) {
        isLoading.value = true
        try {
            const session = await aiApi.getSessionHistory(sid)
            sessionId.value = session.id
            messages.value = session.messages
        } catch (e) {
            console.error('加载会话历史失败:', e)
            throw e
        } finally {
            isLoading.value = false
        }
    }

    return {
        // 状态
        messages,
        sessionId,
        isLoading,
        quickQuestions,
        error,

        // 计算属性
        hasMessages,
        lastMessage,

        // 方法
        initSession,
        fetchQuickQuestions,
        sendMessage,
        sendMessageStream,
        clearMessages,
        newConversation,
        loadSessionHistory,
    }
})
