<template>
  <div class="amount-input">
    <div class="quick-amounts">
      <button
        v-for="quickAmount in quickAmounts"
        :key="quickAmount"
        @click="selectQuickAmount(quickAmount)"
        class="quick-amount-btn"
      >
        {{ quickAmount }}
      </button>
    </div>
    <div class="input-wrapper">
      <span class="currency">{{ currency }}</span>
      <input
        type="number"
        :value="modelValue"
        @input="onInput"
        @blur="onBlur"
        :placeholder="placeholder"
        step="0.01"
        min="0"
        class="amount-field"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue?: number
  currency?: string
  placeholder?: string
  quickAmounts?: number[]
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  currency: 'CNY',
  placeholder: '0.00',
  quickAmounts: () => [10, 50, 100, 500, 1000]
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

function onInput(event: Event) {
  const target = event.target as HTMLInputElement
  const value = parseFloat(target.value) || 0
  emit('update:modelValue', value)
}

function onBlur(event: Event) {
  const target = event.target as HTMLInputElement
  const value = parseFloat(target.value) || 0
  target.value = value.toFixed(2)
  emit('update:modelValue', value)
}

function selectQuickAmount(amount: number) {
  emit('update:modelValue', amount)
}
</script>

<style scoped>
.amount-input {
  width: 100%;
}

.quick-amounts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.quick-amount-btn {
  flex: 1;
  min-width: 60px;
  padding: 8px 12px;
  background: var(--f7-theme-color);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-amount-btn:hover {
  opacity: 0.8;
  transform: translateY(-1px);
}

.quick-amount-btn:active {
  transform: translateY(0);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: white;
}

.currency {
  font-size: 16px;
  font-weight: 500;
  color: #666;
  margin-right: 8px;
}

.amount-field {
  flex: 1;
  border: none;
  outline: none;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.amount-field::placeholder {
  color: #ccc;
}

/* 移除数字输入框的箭头 */
.amount-field::-webkit-outer-spin-button,
.amount-field::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.amount-field[type=number] {
  -moz-appearance: textfield;
}
</style>
