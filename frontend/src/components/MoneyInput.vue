<template>
  <van-field
    class="money-input"
    :model-value="modelValue"
    :label="label"
    type="text"
    inputmode="decimal"
    placeholder="0.00"
    :error-message="error"
    @update:model-value="onInput"
  >
    <template #left-icon>
      <span class="money-currency">{{ currency }}</span>
    </template>
  </van-field>
</template>

<script setup lang="ts">
import { normalizeAmountInput } from '../utils/decimal'

withDefaults(defineProps<{
  modelValue: string
  label?: string
  currency?: string
  error?: string
}>(), {
  label: '金额',
  currency: 'CNY',
  error: '',
})

const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

function onInput(value: string | number) {
  emit('update:modelValue', normalizeAmountInput(String(value)))
}
</script>

<style scoped>
.money-input { padding-top: 18px; padding-bottom: 18px; }
.money-input :deep(.van-field__control) { color: var(--bm-text); font-size: 28px; font-weight: 700; letter-spacing: -.02em; }
.money-currency { margin-right: 8px; color: var(--bm-primary); font-size: 13px; font-weight: 700; }
</style>
