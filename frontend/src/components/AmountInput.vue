<template>
  <div class="amount-input-container">
    <!-- Display Area (Click to open keypad) -->
    <div class="amount-display" @click="openKeypad" :class="{ 'focused': isKeypadOpen }">
      <span class="currency-symbol">{{ currencySymbol }}</span>
      <span class="value-text">{{ displayValue }}</span>
      <span class="cursor" v-if="isKeypadOpen">|</span>
    </div>

    <!-- Keypad Sheet -->
    <f7-sheet
      class="amount-keypad-sheet"
      :opened="isKeypadOpen"
      @sheet:closed="onSheetClosed"
      style="height: auto;"
      backdrop
      close-by-backdrop-click
      swipe-to-close
    >
        <div class="keypad-grid">
            <button class="key-btn number-key" @click="append('1')">1</button>
            <button class="key-btn number-key" @click="append('2')">2</button>
            <button class="key-btn number-key" @click="append('3')">3</button>
            <button class="key-btn action-key" @click="handleDelete">
                 <i class="f7-icons">delete_left</i>
            </button>

            <button class="key-btn number-key" @click="append('4')">4</button>
            <button class="key-btn number-key" @click="append('5')">5</button>
            <button class="key-btn number-key" @click="append('6')">6</button>
            <button class="key-btn op-key" @click="append('+')">+</button>

            <button class="key-btn number-key" @click="append('7')">7</button>
            <button class="key-btn number-key" @click="append('8')">8</button>
            <button class="key-btn number-key" @click="append('9')">9</button>
            <button class="key-btn op-key" @click="append('-')">-</button>

            <button class="key-btn number-key" @click="append('.')">.</button>
            <button class="key-btn number-key" @click="append('0')">0</button>
            <button class="key-btn action-key highlight" style="grid-column: span 2" @click="handleOK">
                确定
            </button>
        </div>
    </f7-sheet>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  modelValue?: number
  allowNegative?: boolean
  currency?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  allowNegative: true,
  currency: 'CNY'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const currencySymbol = computed(() => {
  const symbols: Record<string, string> = {
    'CNY': '¥',
    'USD': '$',
    'HKD': 'HK$',
    'EUR': '€',
    'JPY': '¥',
    'GBP': '£'
  }
  return symbols[props.currency || 'CNY'] || props.currency || ''
})

const isKeypadOpen = ref(false)
const expression = ref('')

// Initialize expression from prop
watch(() => props.modelValue, (newVal) => {
    if (!isKeypadOpen.value) {
        expression.value = newVal ? newVal.toString() : ''
    }
}, { immediate: true })

const displayValue = computed(() => {
    return expression.value || '0.00'
})



function openKeypad() {
    isKeypadOpen.value = true
    // If 0, start clean?
    if (expression.value === '0' || expression.value === '0.00') {
        expression.value = ''
    }
}

function closeKeypad() {
    calculate()
    isKeypadOpen.value = false
}

function onSheetClosed() {
    // Ensure we calculate/save when sheet is closed (e.g. via swipe or click outside)
    calculate()
    isKeypadOpen.value = false
}

function append(char: string) {
    // Prevent multiple dots
    if (char === '.') {
        // Find last number segment
        const parts = expression.value.split(/[\+\-]/)
        const currentNum = parts[parts.length - 1]
        if (currentNum && currentNum.includes('.')) return
    }
    
    // Prevent multiple operators
    if (['+', '-'].includes(char)) {
        const lastChar = expression.value.slice(-1)
        if (['+', '-'].includes(lastChar)) {
            expression.value = expression.value.slice(0, -1) + char
            return
        }
        if (expression.value === '' && char === '+') return // Don't start with +
        // Allowed to start with - for negative
    }

    expression.value += char
}

function handleDelete() {
    if (expression.value.length > 0) {
        expression.value = expression.value.slice(0, -1)
    }
}

function calculate() {
    try {
        if (!expression.value) {
             emit('update:modelValue', 0)
             return
        }
        // Safe evaluation
        // Replace potential issues
        let sanitized = expression.value.replace(/[^0-9\+\-\.]/g, '')
        // Clean trailing operators
        if (['+', '-'].includes(sanitized.slice(-1))) {
            sanitized = sanitized.slice(0, -1)
        }
        
        let result = Function('"use strict";return (' + sanitized + ')')()
        
        // Handle constraint
        if (!props.allowNegative && result < 0) {
            // Revert or Clamp?
            // Requirement says "Transfer: Only positive". 
            // Better to just set to positive? Or 0? Or warn?
            // "Only positive" usually means absolute value for Entry, but let's clamp to 0 or warning.
            // Since this is a keypad behavior, let's clamp 0 if negative not allowed.
            result = 0 
        }

        // Float precision
        result = Math.round(result * 100) / 100
        
        emit('update:modelValue', result)
        expression.value = result.toString()
    } catch (e) {
        // Error in expression
    }
}

function handleOK() {
    closeKeypad()
}

</script>

<style scoped>
.amount-input-container {
    width: 100%;
}

.amount-display {
    display: flex;
    align-items: center;
    justify-content: flex-end; /* Align right like numbers usually are */
    font-size: 24px;
    font-weight: 600;
    padding: 10px 0;
    border-bottom: 2px solid transparent;
    transition: border-color 0.2s;
    min-height: 48px;
}

.amount-display.focused {
    border-bottom-color: var(--f7-theme-color);
}

.currency-symbol {
    font-size: 0.8em;
    margin-right: 4px;
    color: #666;
}

.value-text {
    color: #333;
}

.cursor {
    margin-left: 2px;
    animation: blink 1s infinite;
    font-weight: 300;
    color: var(--f7-theme-color);
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.keypad-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    padding: 8px;
    background: #f0f0f5;
    padding-bottom: calc(8px + var(--f7-safe-area-bottom));
}

.key-btn {
    appearance: none;
    border: none;
    background: white;
    border-radius: 5px;
    font-size: 20px;
    font-weight: 500;
    color: #000;
    padding: 15px 0;
    box-shadow: 0 1px 1px rgba(0,0,0,0.2);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.key-btn:active {
    background: #e5e5e5;
}

.action-key {
    background: #e4e4e9;
}

.highlight {
    background: var(--f7-theme-color);
    color: white;
}
.highlight:active {
    opacity: 0.8;
}

.op-key {
    background: #ffcc00; /* Calculator orange or just distinct */
    background: #f4d03f;
    color: black;
}
</style>
