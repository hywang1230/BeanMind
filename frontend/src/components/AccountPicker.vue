<template>
  <SelectPickerField
    :model-value="modelValue"
    :label="label"
    :options="options"
    :error="error"
    placeholder="请选择账户"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Account } from '../api/accounts'
import SelectPickerField from './SelectPickerField.vue'

const props = withDefaults(defineProps<{
  modelValue: string
  accounts: Account[]
  label?: string
  prefixes?: string[]
  error?: string
}>(), { label: '账户', prefixes: () => [], error: '' })
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

const flatten = (accounts: Account[]): Account[] => accounts.flatMap(account => [account, ...flatten(account.children || [])])
const filtered = computed(() => {
  const all = flatten(props.accounts)
  return props.prefixes.length ? all.filter(item => props.prefixes.some(prefix => item.name.startsWith(prefix))) : all
})
const options = computed(() => [
  { text: '请选择账户', value: '' },
  ...filtered.value.map(account => ({ text: account.name, value: account.name })),
])
</script>
