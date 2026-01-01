<template>
    <div class="ptr-wrapper" ref="wrapperRef">
        <!-- 下拉刷新指示器 -->
        <div class="ptr-indicator" :class="{ 'ptr-visible': pullDistance > 10 }" :style="indicatorStyle">
            <div v-if="!refreshing" class="ptr-arrow" :class="{ 'rotate': isOverThreshold }">
                <f7-icon ios="f7:arrow_down" size="20"></f7-icon>
            </div>
            <div v-else class="ptr-spinner">
                <f7-preloader size="20"></f7-preloader>
            </div>
            <span class="ptr-text">{{ statusText }}</span>
        </div>

        <!-- 内容区域 -->
        <div class="ptr-content" :style="contentStyle">
            <slot></slot>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { f7Icon, f7Preloader } from 'framework7-vue'

const props = defineProps<{
    disabled?: boolean
}>()

const emit = defineEmits<{
    (e: 'refresh', done: () => void): void
}>()

// 配置参数
const THRESHOLD = 60 // 触发刷新的阈值（像素）
const MAX_PULL = 100 // 最大下拉距离

// 状态
const wrapperRef = ref<HTMLElement | null>(null)
const pullDistance = ref(0)
const refreshing = ref(false)
const isPulling = ref(false)
const startY = ref(0)
const scrollContainer = ref<Element | null>(null)
const isOverThreshold = computed(() => pullDistance.value >= THRESHOLD)

// 样式计算
const indicatorStyle = computed(() => ({
    height: `${Math.min(pullDistance.value, THRESHOLD)}px`,
}))

const contentStyle = computed(() => ({
    transform: pullDistance.value > 0 ? `translateY(${pullDistance.value}px)` : 'none',
    transition: isPulling.value ? 'none' : 'transform 0.3s ease-out'
}))

const statusText = computed(() => {
    if (refreshing.value) return '刷新中...'
    if (isOverThreshold.value) return '释放刷新'
    return '下拉刷新'
})

// 判断是否在顶部
function isAtTop(): boolean {
    if (scrollContainer.value) {
        return scrollContainer.value.scrollTop <= 0
    }
    return true
}

// 触摸事件处理
function onTouchStart(e: Event) {
    if (props.disabled || refreshing.value) return

    const touchEvent = e as TouchEvent
    // 记录起始位置，稍后判断是否在顶部
    startY.value = touchEvent.touches[0]!.clientY
    isPulling.value = false
}

function onTouchMove(e: Event) {
    if (props.disabled || refreshing.value) return

    const touchEvent = e as TouchEvent
    const currentY = touchEvent.touches[0]!.clientY
    const diff = currentY - startY.value

    // 只处理向下拉动且在顶部
    if (diff <= 0 || !isAtTop()) {
        if (pullDistance.value > 0) {
            pullDistance.value = 0
        }
        isPulling.value = false
        return
    }

    isPulling.value = true

    // 使用阻尼效果
    const resistance = diff > THRESHOLD ? 0.3 : 0.5
    pullDistance.value = Math.min(diff * resistance, MAX_PULL)

    // 阻止页面滚动（只有在正在下拉时）
    if (pullDistance.value > 0) {
        e.preventDefault()
    }
}

function onTouchEnd() {
    if (props.disabled || refreshing.value) return

    isPulling.value = false

    if (isOverThreshold.value) {
        // 触发刷新
        refreshing.value = true
        pullDistance.value = THRESHOLD

        emit('refresh', () => {
            // 刷新完成回调
            refreshing.value = false
            pullDistance.value = 0
        })
    } else {
        // 回弹
        pullDistance.value = 0
    }
}

onMounted(() => {
    // 找到滚动容器（f7-tab.page-content）
    const wrapper = wrapperRef.value
    if (wrapper) {
        scrollContainer.value = wrapper.closest('.page-content')

        // 在滚动容器上监听触摸事件
        const target = scrollContainer.value || wrapper
        target.addEventListener('touchstart', onTouchStart, { passive: true })
        target.addEventListener('touchmove', onTouchMove, { passive: false })
        target.addEventListener('touchend', onTouchEnd, { passive: true })
    }
})

onUnmounted(() => {
    const wrapper = wrapperRef.value
    if (wrapper) {
        const target = scrollContainer.value || wrapper
        target.removeEventListener('touchstart', onTouchStart)
        target.removeEventListener('touchmove', onTouchMove)
        target.removeEventListener('touchend', onTouchEnd)
    }
})
</script>

<style scoped>
.ptr-wrapper {
    position: relative;
    width: 100%;
    min-height: 100%;
}

.ptr-indicator {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    overflow: hidden;
    background: var(--bg-primary);
    z-index: 100;
    opacity: 0;
    transition: opacity 0.2s ease;
}

.ptr-indicator.ptr-visible {
    opacity: 1;
}

.ptr-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s ease;
    color: var(--ios-blue);
}

.ptr-arrow.rotate {
    transform: rotate(180deg);
}

.ptr-spinner {
    display: flex;
    align-items: center;
    justify-content: center;
}

.ptr-text {
    font-size: 13px;
    color: #8e8e93;
}

.ptr-content {
    position: relative;
    width: 100%;
}
</style>
