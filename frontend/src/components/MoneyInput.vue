<template>
  <van-field
    :model-value="modelValue"
    :label="label"
    inputmode="decimal"
    placeholder="0.00"
    :error-message="error"
    @update:model-value="onInput"
  >
    <template #left-icon>{{ currency }}</template>
  </van-field>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ modelValue: string; label?: string; currency?: string; error?: string }>(), {
  label: '金额',
  currency: 'CNY',
  error: '',
})
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()
function onInput(value: string | number) {
  const text = String(value).replace(/[^0-9.]/g, '')
  const [integer = '', ...decimals] = text.split('.')
  emit('update:modelValue', decimals.length ? `${integer}.${decimals.join('')}` : integer)
}
</script>
