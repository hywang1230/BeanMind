<template>
  <van-field :label="label" :error-message="error">
    <template #input>
      <select class="native-select" :value="modelValue" @change="onChange">
        <option value="">请选择账户</option>
        <option v-for="account in filtered" :key="account.name" :value="account.name">
          {{ account.name }}
        </option>
      </select>
    </template>
  </van-field>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Account } from '../api/accounts'

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
function onChange(event: Event) {
  emit('update:modelValue', (event.target as HTMLSelectElement).value)
}
</script>
