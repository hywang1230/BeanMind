<template>
  <div class="ai-page">
    <!-- 顶部标题栏 -->
    <div class="ai-header">
      <div class="header-title">
        <f7-icon f7="sparkles" class="header-icon" />
        <span>AI 智能助手</span>
      </div>
      <f7-button 
        v-if="aiStore.hasMessages" 
        @click="handleNewChat"
        class="new-chat-btn"
      >
        <f7-icon f7="plus_bubble" size="20" />
      </f7-button>
    </div>

    <!-- 消息区域 -->
    <div class="messages-container" ref="messagesContainer">
      <!-- 欢迎界面（无消息时显示） -->
      <div v-if="!aiStore.hasMessages" class="welcome-section">
        <div class="welcome-icon">
          <f7-icon f7="sparkles" size="48" />
        </div>
        <h2 class="welcome-title">您好，我是您的财务助手</h2>
        <p class="welcome-subtitle">我可以帮您分析消费、查看账单、提供理财建议</p>
        
        <!-- 快捷问题 -->
        <div class="quick-questions">
          <div 
            v-for="question in aiStore.quickQuestions" 
            :key="question.id"
            class="quick-question-card"
            @click="handleQuickQuestion(question.text)"
          >
            <f7-icon :f7="question.icon || 'lightbulb'" class="question-icon" />
            <span class="question-text">{{ question.text }}</span>
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-else class="messages-list">
        <div 
          v-for="message in aiStore.messages" 
          :key="message.id"
          class="message-item"
          :class="[`message-${message.role}`]"
        >
          <!-- 头像 -->
          <div class="message-avatar">
            <f7-icon 
              :f7="message.role === 'user' ? 'person_fill' : 'sparkles'" 
              :class="message.role === 'user' ? 'user-avatar' : 'ai-avatar'"
            />
          </div>
          
          <!-- 消息内容 -->
          <div class="message-content">
            <div class="message-bubble">
              <div class="message-text" v-html="formatMessage(message.content)"></div>
            </div>
            <div class="message-time">{{ formatTime(message.created_at) }}</div>
          </div>
        </div>
        
        <!-- 加载指示器 -->
        <div v-if="aiStore.isLoading" class="loading-indicator">
          <div class="ai-loading-avatar">
            <f7-icon f7="sparkles" class="ai-avatar" />
          </div>
          <div class="loading-content">
            <div class="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div class="loading-time">{{ formatTime(new Date().toISOString()) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-container">
      <!-- 输入框 -->
      <div class="input-wrapper">
        <textarea 
          v-model="inputMessage"
          @keydown.enter.exact.prevent="handleSend"
          placeholder="输入您的问题..."
          rows="1"
          class="message-input"
          ref="inputRef"
          :disabled="aiStore.isLoading"
        ></textarea>
        <f7-button 
          @click="handleSend"
          :disabled="!inputMessage.trim() || aiStore.isLoading"
          class="send-btn"
          :class="{ 'active': inputMessage.trim() && !aiStore.isLoading }"
        >
          <f7-icon f7="arrow_up_circle_fill" size="32" />
        </f7-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { f7Icon, f7Button } from 'framework7-vue'
import { useAIStore } from '../../stores/ai'
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true, // 支持换行
  gfm: true, // 支持 GitHub 风格 Markdown
})

const aiStore = useAIStore()
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// 初始化
onMounted(async () => {
  aiStore.initSession()
  await aiStore.fetchQuickQuestions()
})

// 监听消息变化，自动滚动到底部
watch(
  () => aiStore.messages.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 监听加载状态变化
watch(
  () => aiStore.isLoading,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 滚动到底部
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 发送消息
async function handleSend() {
  const message = inputMessage.value.trim()
  if (!message || aiStore.isLoading) return
  
  inputMessage.value = ''
  await aiStore.sendMessage(message)
}

// 点击快捷问题
async function handleQuickQuestion(question: string) {
  await aiStore.sendMessage(question)
}

// 新建对话
function handleNewChat() {
  aiStore.newConversation()
}

// 格式化消息（使用 marked 支持完整 Markdown）
function formatMessage(content: string): string {
  if (!content) return ''
  
  // 使用 marked 解析 Markdown
  const html = marked.parse(content) as string
  return html
}

// 格式化时间
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.ai-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--f7-page-bg-color);
}

/* 顶部标题栏 */
.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--f7-bars-bg-color);
  border-bottom: 1px solid var(--f7-bars-border-color);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--f7-text-color);
}

.header-icon {
  color: #8b5cf6;
}

.new-chat-btn {
  --f7-button-text-color: var(--f7-theme-color);
  min-width: auto;
  padding: 0 8px;
}

/* 消息容器 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  scroll-behavior: smooth;
}

/* 欢迎界面 */
.welcome-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 20px;
  text-align: center;
}

.welcome-icon {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(139, 92, 246, 0.3);
}

.welcome-icon :deep(i) {
  color: white;
}

.welcome-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--f7-text-color);
  margin: 0 0 8px;
}

.welcome-subtitle {
  font-size: 15px;
  color: var(--f7-text-color);
  opacity: 0.6;
  margin: 0 0 32px;
  max-width: 280px;
}

/* 快捷问题 */
.quick-questions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 400px;
}

.quick-question-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--f7-card-bg-color);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.quick-question-card:hover {
  background: var(--f7-card-expandable-bg-color);
  border-color: var(--f7-theme-color);
  transform: translateY(-2px);
}

.quick-question-card:active {
  transform: scale(0.98);
}

.question-icon {
  color: #8b5cf6;
  font-size: 20px;
  flex-shrink: 0;
}

.question-text {
  font-size: 14px;
  color: var(--f7-text-color);
  text-align: left;
  line-height: 1.3;
}

/* 消息列表 */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-avatar {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
}

.ai-avatar {
  background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
  color: white;
}

.message-content {
  flex: 1;
  min-width: 0;
  max-width: 95%;
}

.message-user .message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 18px;
  line-height: 1.5;
  word-wrap: break-word;
}

.message-user .message-bubble {
  background: var(--f7-theme-color);
  color: white;
  border-bottom-right-radius: 6px;
}

.message-assistant .message-bubble {
  background: var(--f7-card-bg-color);
  color: var(--f7-text-color);
  border-bottom-left-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.message-text {
  font-size: 15px;
  line-height: 1.6;
}

/* Markdown 样式 */
.message-text :deep(p) {
  margin: 0 0 12px 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4),
.message-text :deep(h5),
.message-text :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  line-height: 1.3;
}

.message-text :deep(h1:first-child),
.message-text :deep(h2:first-child),
.message-text :deep(h3:first-child) {
  margin-top: 0;
}

.message-text :deep(h1) { font-size: 1.5em; }
.message-text :deep(h2) { font-size: 1.3em; }
.message-text :deep(h3) { font-size: 1.15em; }
.message-text :deep(h4) { font-size: 1em; }

/* 表格样式 */
.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 14px;
  overflow-x: auto;
  display: block;
}

.message-text :deep(thead) {
  background: rgba(0, 0, 0, 0.06);
}

.message-text :deep(th),
.message-text :deep(td) {
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  text-align: left;
  white-space: nowrap;
}

.message-text :deep(th) {
  font-weight: 600;
}

.message-text :deep(tbody tr:nth-child(even)) {
  background: rgba(0, 0, 0, 0.02);
}

/* 列表样式 */
.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.message-text :deep(li) {
  margin: 4px 0;
}

/* 引用样式 */
.message-text :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 4px solid #8b5cf6;
  background: rgba(139, 92, 246, 0.08);
  border-radius: 0 8px 8px 0;
}

.message-text :deep(blockquote p) {
  margin: 0;
}

/* 水平线 */
.message-text :deep(hr) {
  border: none;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  margin: 16px 0;
}

/* 代码样式 */
.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.message-text :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
}

/* 链接样式 */
.message-text :deep(a) {
  color: #8b5cf6;
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

/* 强调样式 */
.message-text :deep(strong) {
  font-weight: 600;
}

.message-text :deep(em) {
  font-style: italic;
}

.message-time {
  font-size: 11px;
  color: var(--f7-text-color);
  opacity: 0.4;
  margin-top: 4px;
  padding: 0 4px;
}

/* 加载指示器 */
.loading-indicator {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

.ai-loading-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
}

.ai-loading-avatar :deep(i) {
  color: white;
}

.loading-content {
  display: flex;
  flex-direction: column;
}

.loading-dots {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: var(--f7-card-bg-color);
  border-radius: 18px;
  border-bottom-left-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.loading-time {
  font-size: 11px;
  color: var(--f7-text-color);
  opacity: 0.4;
  margin-top: 4px;
  padding: 0 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--f7-theme-color);
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 输入区域 */
.input-container {
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--f7-bars-bg-color);
  border-top: 1px solid var(--f7-bars-border-color);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--f7-input-bg-color, var(--f7-card-bg-color));
  border-radius: 24px;
  padding: 8px 8px 8px 16px;
  border: 1px solid var(--f7-input-border-color, rgba(0, 0, 0, 0.1));
}

.message-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  line-height: 1.4;
  resize: none;
  max-height: 120px;
  color: var(--f7-text-color);
  outline: none;
  padding: 6px 0;
}

.message-input::placeholder {
  color: var(--f7-input-placeholder-color);
}

.message-input:disabled {
  opacity: 0.6;
}

.send-btn {
  --f7-button-text-color: #d1d5db;
  min-width: auto;
  padding: 0;
  transition: all 0.2s ease;
}

.send-btn.active {
  --f7-button-text-color: var(--f7-theme-color);
}

.send-btn:active {
  transform: scale(0.9);
}

/* 暗黑模式适配 */
:global(.theme-dark) .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.1);
}

:global(.theme-dark) .message-text :deep(pre) {
  background: rgba(255, 255, 255, 0.08);
}

:global(.theme-dark) .message-text :deep(thead) {
  background: rgba(255, 255, 255, 0.08);
}

:global(.theme-dark) .message-text :deep(th),
:global(.theme-dark) .message-text :deep(td) {
  border-color: rgba(255, 255, 255, 0.12);
}

:global(.theme-dark) .message-text :deep(tbody tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.03);
}

:global(.theme-dark) .message-text :deep(blockquote) {
  background: rgba(139, 92, 246, 0.12);
}

:global(.theme-dark) .message-text :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.12);
}

:global(.theme-dark) .user-avatar,
:global(.theme-dark) .ai-avatar {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
</style>
