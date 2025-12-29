import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { aiApi, type ChatMessage, type QuickQuestion, type StreamChunk } from '../api/ai'

// 生成 UUID（使用浏览器内置 API）
function generateId(): string {
    return crypto.randomUUID()
}

export const useAIStore = defineStore('ai', () => {
    // 状态
    const messages = ref<ChatMessage[]>([])
    const sessionId = ref<string>('')
    const isStreaming = ref(false)
    const currentStreamingContent = ref('')
    const quickQuestions = ref<QuickQuestion[]>([])
    const loading = ref(false)
    const error = ref<string | null>(null)
    
    // 当前请求的 AbortController
    let currentAbortController: AbortController | null = null

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
                { id: 'q2', text: '最近消费趋势', icon: 'chart_line_uptrend_xyaxis' },
                { id: 'q3', text: '上月账单总结', icon: 'doc_text' },
                { id: 'q4', text: '今日消费情况', icon: 'calendar_badge_clock' },
            ]
        }
    }

    // 发送消息（流式）
    async function sendMessage(content: string) {
        if (!content.trim() || isStreaming.value) return

        initSession()
        error.value = null
        
        // 添加用户消息
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: content.trim(),
            created_at: new Date().toISOString(),
        }
        messages.value.push(userMessage)
        
        // 创建 AI 消息占位
        const assistantMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            is_streaming: true,
        }
        messages.value.push(assistantMessage)
        
        isStreaming.value = true
        currentStreamingContent.value = ''
        
        // 构建历史（不包含当前的占位消息）
        const history = messages.value
            .slice(0, -1)  // 排除占位消息
            .filter(m => !m.is_streaming)
            .map(m => ({ role: m.role, content: m.content }))
        
        // 发起流式请求
        currentAbortController = aiApi.chatStream(
            {
                message: content.trim(),
                session_id: sessionId.value,
                history,
            },
            {
                onChunk: (chunk: StreamChunk) => {
                    currentStreamingContent.value += chunk.content
                    // 更新最后一条消息的内容
                    const lastMsg = messages.value[messages.value.length - 1]
                    if (lastMsg && lastMsg.role === 'assistant') {
                        lastMsg.content = currentStreamingContent.value
                    }
                    // 更新 session_id
                    if (chunk.session_id) {
                        sessionId.value = chunk.session_id
                    }
                },
                onDone: (fullContent: string, sid: string, msgId: string) => {
                    // 更新最终内容
                    const lastMsg = messages.value[messages.value.length - 1]
                    if (lastMsg && lastMsg.role === 'assistant') {
                        lastMsg.content = fullContent
                        lastMsg.is_streaming = false
                        if (msgId) lastMsg.id = msgId
                    }
                    if (sid) sessionId.value = sid
                    
                    isStreaming.value = false
                    currentStreamingContent.value = ''
                    currentAbortController = null
                },
                onError: (errorMsg: string) => {
                    error.value = errorMsg
                    // 更新错误消息
                    const lastMsg = messages.value[messages.value.length - 1]
                    if (lastMsg && lastMsg.role === 'assistant') {
                        lastMsg.content = `抱歉，处理您的请求时出现了问题：${errorMsg}`
                        lastMsg.is_streaming = false
                    }
                    
                    isStreaming.value = false
                    currentStreamingContent.value = ''
                    currentAbortController = null
                },
            }
        )
    }

    // 停止当前流式输出
    function stopStreaming() {
        if (currentAbortController) {
            currentAbortController.abort()
            currentAbortController = null
        }
        
        // 标记最后一条消息为完成
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.is_streaming) {
            lastMsg.is_streaming = false
            if (!lastMsg.content) {
                lastMsg.content = '（已停止）'
            }
        }
        
        isStreaming.value = false
        currentStreamingContent.value = ''
    }

    // 清空消息
    function clearMessages() {
        stopStreaming()
        messages.value = []
        error.value = null
        
        // 如果有会话，清空服务端会话
        if (sessionId.value) {
            aiApi.clearSession(sessionId.value).catch(console.error)
        }
    }

    // 新建对话
    function newConversation() {
        clearMessages()
        sessionId.value = generateId()
    }

    // 加载会话历史
    async function loadSessionHistory(sid: string) {
        loading.value = true
        try {
            const session = await aiApi.getSessionHistory(sid)
            sessionId.value = session.id
            messages.value = session.messages
        } catch (e) {
            console.error('加载会话历史失败:', e)
            throw e
        } finally {
            loading.value = false
        }
    }

    return {
        // 状态
        messages,
        sessionId,
        isStreaming,
        currentStreamingContent,
        quickQuestions,
        loading,
        error,
        
        // 计算属性
        hasMessages,
        lastMessage,
        
        // 方法
        initSession,
        fetchQuickQuestions,
        sendMessage,
        stopStreaming,
        clearMessages,
        newConversation,
        loadSessionHistory,
    }
})

