<template>
  <div class="money-input">
    <button
      type="button"
      class="money-display"
      :class="{ focused: keypadOpen, 'has-error': Boolean(error) }"
      @click="openKeypad"
    >
      <span class="money-label">{{ label }}</span>
      <span class="money-value-row">
        <span class="money-currency">{{ currency }}</span>
        <span class="money-value">{{ displayValue }}</span>
        <span v-if="keypadOpen" class="money-cursor">|</span>
      </span>
    </button>
    <div v-if="error" class="money-error">{{ error }}</div>

    <van-popup
      v-model:show="keypadOpen"
      position="bottom"
      round
      :safe-area-inset-bottom="true"
      @closed="onPopupClosed"
    >
      <div class="amount-keypad" role="group" aria-label="金额键盘">
        <div class="keypad-preview">
          <span class="keypad-preview-currency">{{ currency }}</span>
          <span class="keypad-preview-value">{{ expression || '0.00' }}</span>
        </div>
        <div class="keypad-grid">
          <button type="button" class="key-btn" @click="onKey('1')">1</button>
          <button type="button" class="key-btn" @click="onKey('2')">2</button>
          <button type="button" class="key-btn" @click="onKey('3')">3</button>
          <button type="button" class="key-btn action-key" aria-label="删除" @click="onKey('delete')">⌫</button>

          <button type="button" class="key-btn" @click="onKey('4')">4</button>
          <button type="button" class="key-btn" @click="onKey('5')">5</button>
          <button type="button" class="key-btn" @click="onKey('6')">6</button>
          <button type="button" class="key-btn op-key" @click="onKey('+')">+</button>

          <button type="button" class="key-btn" @click="onKey('7')">7</button>
          <button type="button" class="key-btn" @click="onKey('8')">8</button>
          <button type="button" class="key-btn" @click="onKey('9')">9</button>
          <button type="button" class="key-btn op-key" @click="onKey('-')">-</button>

          <button type="button" class="key-btn" @click="onKey('.')">.</button>
          <button type="button" class="key-btn" @click="onKey('0')">0</button>
          <button type="button" class="key-btn confirm-key" @click="confirmKeypad">确定</button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  appendAmountKey,
  evaluateAmountExpression,
  expressionFromModel,
  type AmountKey,
} from '../utils/amountExpression'
import { formatAmountDisplay } from '../utils/decimal'

const props = withDefaults(defineProps<{
  modelValue: string
  label?: string
  currency?: string
  error?: string
  allowNegative?: boolean
}>(), {
  label: '金额',
  currency: 'CNY',
  error: '',
  allowNegative: true,
})

const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

const keypadOpen = ref(false)
const expression = ref('')
const committedOnClose = ref(false)

const displayValue = computed(() => {
  if (keypadOpen.value) return expression.value || '0.00'
  if (!props.modelValue) return '0.00'
  try {
    return formatAmountDisplay(props.modelValue)
  } catch {
    return props.modelValue
  }
})

watch(() => props.modelValue, (value) => {
  if (!keypadOpen.value) {
    expression.value = expressionFromModel(value)
  }
}, { immediate: true })

function openKeypad() {
  expression.value = expressionFromModel(props.modelValue)
  committedOnClose.value = false
  keypadOpen.value = true
}

function commitExpression() {
  const result = evaluateAmountExpression(expression.value, {
    allowNegative: props.allowNegative,
  })
  emit('update:modelValue', result)
  expression.value = result
  committedOnClose.value = true
}

function confirmKeypad() {
  commitExpression()
  keypadOpen.value = false
}

function onPopupClosed() {
  if (!committedOnClose.value) {
    commitExpression()
  }
  keypadOpen.value = false
  committedOnClose.value = false
}

function onKey(key: AmountKey) {
  expression.value = appendAmountKey(expression.value, key, {
    allowNegative: props.allowNegative,
  })
}
</script>

<style scoped>
.money-input {
  padding: 12px 16px 4px;
}

.money-display {
  appearance: none;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px 0 12px;
  text-align: left;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}

.money-display.focused {
  border-bottom-color: var(--bm-primary);
}

.money-display.has-error {
  border-bottom-color: var(--bm-expense);
}

.money-label {
  display: block;
  margin-bottom: 8px;
  color: var(--bm-muted);
  font-size: 13px;
  font-weight: 600;
}

.money-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-height: 36px;
}

.money-currency {
  color: var(--bm-primary);
  font-size: 13px;
  font-weight: 700;
}

.money-value {
  color: var(--bm-text);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.money-cursor {
  color: var(--bm-primary);
  font-weight: 300;
  animation: money-blink 1s step-end infinite;
}

.money-error {
  margin-top: 6px;
  color: var(--bm-expense);
  font-size: 12px;
}

.amount-keypad {
  padding: 12px 12px calc(12px + env(safe-area-inset-bottom, 0px));
  background: var(--bm-bg);
}

.keypad-preview {
  display: flex;
  justify-content: flex-end;
  align-items: baseline;
  gap: 8px;
  min-height: 36px;
  margin-bottom: 10px;
  padding: 0 4px;
}

.keypad-preview-currency {
  color: var(--bm-muted);
  font-size: 13px;
  font-weight: 600;
}

.keypad-preview-value {
  color: var(--bm-text);
  font-size: 24px;
  font-weight: 700;
  word-break: break-all;
  text-align: right;
}

.keypad-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.key-btn {
  appearance: none;
  border: 1px solid var(--bm-border);
  border-radius: 10px;
  background: var(--bm-surface);
  color: var(--bm-text);
  font-size: 20px;
  font-weight: 600;
  min-height: 52px;
  cursor: pointer;
}

.key-btn:active {
  background: var(--bm-primary-soft);
}

.action-key {
  background: var(--bm-control);
  color: var(--bm-muted);
}

.op-key {
  background: #fff7ed;
  color: #c2410c;
  border-color: #fed7aa;
}

.confirm-key {
  grid-column: span 2;
  background: var(--bm-primary);
  border-color: var(--bm-primary);
  color: #fff;
}

.confirm-key:active {
  opacity: 0.88;
}

@keyframes money-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
