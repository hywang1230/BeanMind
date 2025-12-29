import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { aiApi, type ChatMessage, type QuickQuestion } from '../api/ai'

// 生成 UUID（使用浏览器内置 API）
function generateId(): string {
    return crypto.randomUUID()
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
                { id: 'q2', text: '最近消费趋势', icon: 'chart_line_uptrend_xyaxis' },
                { id: 'q3', text: '上月账单总结', icon: 'doc_text' },
                { id: 'q4', text: '今日消费情况', icon: 'calendar_badge_clock' },
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
        clearMessages()
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
        clearMessages,
        newConversation,
        loadSessionHistory,
    }
})
