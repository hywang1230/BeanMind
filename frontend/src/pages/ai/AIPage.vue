<template>
  <f7-page>
    <f7-navbar>
      <f7-nav-left>
        <f7-link icon-ios="f7:chevron_left" icon-md="material:arrow_back" @click="goBack" />
      </f7-nav-left>
      <f7-nav-title>AI 智能助手</f7-nav-title>
      <f7-nav-right>
        <f7-link v-if="aiStore.hasMessages" @click="handleNewChat" icon-ios="f7:plus" icon-md="material:add" />
      </f7-nav-right>
    </f7-navbar>

    <div class="ai-page-content">

      <!-- 消息区域 -->
      <div class="messages-container" ref="messagesContainer">
        <!-- 欢迎界面（无消息时显示） -->
        <div v-if="!aiStore.hasMessages" class="welcome-section">
          <div class="welcome-content">
            <div class="welcome-icon">
              <f7-icon f7="sparkles" size="32" />
            </div>
            <h2 class="welcome-title">财务助手</h2>
            <p class="welcome-subtitle">分析消费、查看账单、提供理财建议</p>

            <!-- 快捷问题 -->
            <div class="quick-questions">
              <div v-for="question in aiStore.quickQuestions" :key="question.id" class="quick-question-card"
                @click="handleQuickQuestion(question.text)">
                <f7-icon :f7="question.icon || 'lightbulb'" class="question-icon" />
                <span class="question-text">{{ question.text }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages-list">
          <div v-for="message in aiStore.messages" :key="message.id" class="message-item"
            :class="[`message-${message.role}`]">
            <!-- 头像 -->
            <div class="message-avatar">
              <f7-icon :f7="message.role === 'user' ? 'person_fill' : 'sparkles'"
                :class="message.role === 'user' ? 'user-avatar' : 'ai-avatar'" />
            </div>

            <!-- 消息内容 -->
            <div class="message-content">
              <div class="message-bubble">
                <div class="message-text" v-html="formatMessage(message.content)"></div>
              </div>
              <div class="message-time">{{ formatTime(message.created_at) }}</div>
            </div>
          </div>

          <!-- 加载指示器（仅在等待 AI 开始回复时显示） -->
          <div v-if="aiStore.isLoading && !isStreamingContent" class="loading-indicator">
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
          <textarea v-model="inputMessage" @keydown.enter.exact.prevent="handleSend" placeholder="输入您的问题..." rows="1"
            class="message-input" ref="inputRef" :disabled="aiStore.isLoading"></textarea>
          <f7-button @click="handleSend" :disabled="!inputMessage.trim() || aiStore.isLoading" class="send-btn"
            :class="{ 'active': inputMessage.trim() && !aiStore.isLoading }">
            <f7-icon f7="arrow_up_circle_fill" size="32" />
          </f7-button>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  f7Page,
  f7Navbar,
  f7NavLeft,
  f7NavTitle,
  f7NavRight,
  f7Link,
  f7Icon,
  f7Button
} from 'framework7-vue'
import { useAIStore } from '../../stores/ai'
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true, // 支持换行
  gfm: true, // 支持 GitHub 风格 Markdown
})

const aiStore = useAIStore()
const router = useRouter()
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

// 返回上一页
function goBack() {
  // 直接导航回主页面，会自动恢复到之前的 tab
  router.push('/')
}

// 初始化
onMounted(async () => {
  // 每次进入页面都开始新的对话
  aiStore.newConversation()
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

// 判断是否正在流式输出内容（用于控制加载指示器显示）
const isStreamingContent = computed(() => {
  const msgs = aiStore.messages
  if (msgs.length === 0) return false
  const lastMsg = msgs[msgs.length - 1]
  // 如果最后一条消息是 AI 消息且有内容，说明正在流式输出
  return lastMsg?.role === 'assistant' && !!lastMsg.content
})

// 发送消息（使用流式输出）
async function handleSend() {
  const message = inputMessage.value.trim()
  if (!message || aiStore.isLoading) return

  inputMessage.value = ''
  await aiStore.sendMessageStream(message)
}

// 点击快捷问题（使用流式输出）
async function handleQuickQuestion(question: string) {
  await aiStore.sendMessageStream(question)
}

// 新建对话
function handleNewChat() {
  aiStore.newConversation()
}

// 格式化消息（使用 marked 支持完整 Markdown，带智能补全）
function formatMessage(content: string): string {
  if (!content) return ''

  let processedContent = content

  // ===== 1. 预处理代码块格式 =====
  // 确保代码块标记 ``` 前后都有换行符，这样 marked 才能正确解析
  // 处理：```json{ -> ```json\n{
  processedContent = processedContent.replace(/```(\w*)\s*([^\n])/g, '```$1\n$2')
  // 处理：}```现在 -> }\n```\n现在
  processedContent = processedContent.replace(/([^\n])```([^\n`])/g, '$1\n```\n$2')
  // 处理：}``` -> }\n```
  processedContent = processedContent.replace(/([^\n])```$/g, '$1\n```')

  // ===== 2. 智能补全未闭合的代码块 =====
  const codeBlockMatches = processedContent.match(/```/g)
  if (codeBlockMatches && codeBlockMatches.length % 2 !== 0) {
    processedContent += '\n```'
  }

  // ===== 3. 补全行内代码 =====
  // 在代码块外检测未闭合的行内代码
  // 先提取所有代码块内容，然后在非代码块部分检测
  const codeBlockRegex = /```[\s\S]*?```/g
  const textWithoutCodeBlocks = processedContent.replace(codeBlockRegex, '')
  const inlineCodeMatches = textWithoutCodeBlocks.match(/(?<!`)`(?!`)/g)
  if (inlineCodeMatches && inlineCodeMatches.length % 2 !== 0) {
    processedContent += '`'
  }

  // ===== 4. 补全粗体 =====
  // 同样需要排除代码块内的内容
  const textForBold = processedContent.replace(codeBlockRegex, '')
  // 简化逻辑：如果 ** 出现奇数次，补全一个
  const totalBoldMarkers = (textForBold.match(/\*\*/g) || []).length
  if (totalBoldMarkers % 2 !== 0) {
    processedContent += '**'
  }

  // ===== 5. 补全斜体 =====
  // 检测单独的 * （不是 ** 的一部分）
  const textForItalic = processedContent.replace(codeBlockRegex, '').replace(/\*\*/g, '')
  const italicMatches = textForItalic.match(/\*/g)
  if (italicMatches && italicMatches.length % 2 !== 0) {
    processedContent += '*'
  }

  // 使用 marked 解析 Markdown
  const html = marked.parse(processedContent) as string
  return html
}

// 格式化时间
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.ai-page-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
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
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 20px;
}

.welcome-content {
  text-align: center;
  max-width: 320px;
  width: 100%;
}

.welcome-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: rgba(0, 122, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.welcome-icon :deep(i) {
  color: var(--ios-blue);
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.welcome-subtitle {
  font-size: 15px;
  color: #8e8e93;
  margin: 0 0 32px;
  line-height: 1.4;
}

/* 快捷问题 */
.quick-questions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.quick-question-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-secondary);
  border-radius: 12px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.quick-question-card:active {
  background: var(--bg-secondary);
  opacity: 0.7;
}

.question-icon {
  color: var(--ios-blue);
  font-size: 20px;
  flex-shrink: 0;
}

.question-text {
  font-size: 15px;
  color: var(--text-primary);
  text-align: left;
  line-height: 1.4;
  flex: 1;
}

/* 消息列表 */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-item {
  display: flex;
  gap: 8px;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
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
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-avatar {
  background: #8e8e93;
  color: white;
}

.ai-avatar {
  background: rgba(0, 122, 255, 0.1);
  color: var(--ios-blue);
}

.message-content {
  flex: 1;
  min-width: 0;
  max-width: 80%;
}

.message-user .message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 18px;
  line-height: 1.4;
  word-wrap: break-word;
}

.message-user .message-bubble {
  background: var(--ios-blue);
  color: white;
  border-bottom-right-radius: 4px;
}

.message-assistant .message-bubble {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.message-text {
  font-size: 15px;
  line-height: 1.5;
}

/* Markdown 样式 */
.message-text :deep(p) {
  margin: 0 0 8px 0;
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
  margin: 12px 0 6px 0;
  font-weight: 600;
  line-height: 1.3;
}

.message-text :deep(h1:first-child),
.message-text :deep(h2:first-child),
.message-text :deep(h3:first-child) {
  margin-top: 0;
}

.message-text :deep(h1) {
  font-size: 1.4em;
}

.message-text :deep(h2) {
  font-size: 1.25em;
}

.message-text :deep(h3) {
  font-size: 1.1em;
}

.message-text :deep(h4) {
  font-size: 1em;
}

/* 表格样式 */
.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 14px;
  overflow-x: auto;
  display: block;
}

.message-text :deep(thead) {
  background: rgba(0, 0, 0, 0.05);
}

.message-text :deep(th),
.message-text :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--separator);
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
  margin: 6px 0;
  padding-left: 20px;
}

.message-text :deep(li) {
  margin: 3px 0;
}

/* 引用样式 */
.message-text :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--ios-blue);
  background: rgba(0, 122, 255, 0.08);
  border-radius: 0 6px 6px 0;
}

.message-text :deep(blockquote p) {
  margin: 0;
}

/* 水平线 */
.message-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--separator);
  margin: 12px 0;
}

/* 代码样式 */
.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 5px;
  border-radius: 3px;
  font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.04);
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
}

.message-text :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
}

/* 链接样式 */
.message-text :deep(a) {
  color: var(--ios-blue);
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
  color: #8e8e93;
  margin-top: 4px;
  padding: 0 4px;
}

/* 加载指示器 */
.loading-indicator {
  display: flex;
  gap: 8px;
  animation: fadeIn 0.2s ease;
}

.ai-loading-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 122, 255, 0.1);
}

.ai-loading-avatar :deep(i) {
  color: var(--ios-blue);
}

.loading-content {
  display: flex;
  flex-direction: column;
}

.loading-dots {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 18px;
  border-bottom-left-radius: 4px;
}

.loading-time {
  font-size: 11px;
  color: #8e8e93;
  margin-top: 4px;
  padding: 0 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8e8e93;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.4;
  }

  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 输入区域 */
.input-container {
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--bg-primary);
  border-top: 0.5px solid var(--separator);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-secondary);
  border-radius: 20px;
  padding: 6px 6px 6px 14px;
  border: 0.5px solid var(--separator);
}

.message-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  line-height: 1.4;
  resize: none;
  max-height: 120px;
  color: var(--text-primary);
  outline: none;
  padding: 6px 0;
}

.message-input::placeholder {
  color: #8e8e93;
}

.message-input:disabled {
  opacity: 0.6;
}

.send-btn {
  --f7-button-text-color: #c7c7cc;
  min-width: auto;
  padding: 0;
  transition: all 0.2s ease;
}

.send-btn.active {
  --f7-button-text-color: var(--ios-blue);
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
  background: rgba(0, 122, 255, 0.15);
}

:global(.theme-dark) .message-text :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.12);
}
</style>
