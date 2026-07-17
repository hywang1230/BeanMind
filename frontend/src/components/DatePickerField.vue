<template>
  <van-field
    :model-value="modelValue"
    :label="label"
    :placeholder="placeholder"
    readonly
    :rules="rules"
    @click="open"
  >
    <template #right-icon>
      <button v-if="clearable && modelValue" type="button" class="field-action" :aria-label="`清空${label}`" @click.stop="clear">
        <van-icon name="cross" />
      </button>
      <van-icon v-else name="arrow" />
    </template>
  </van-field>
  <van-calendar
    v-model:show="show"
    :title="`选择${label}`"
    :default-date="selected"
    :min-date="minDate"
    :max-date="maxDate"
    switch-mode="year-month"
    @confirm="confirm"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  label: string
  placeholder?: string
  rules?: Array<Record<string, unknown>>
  clearable?: boolean
}>(), { placeholder: '请选择日期', rules: () => [], clearable: false })
const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
}>()
const show = ref(false)
const selected = ref<Date>(parseDate(props.modelValue))
const minDate = new Date(2000, 0, 1)
const maxDate = new Date(2100, 11, 31)

function parseDate(value?: string) {
  const parts = value?.split('-').map(Number)
  if (parts?.length === 3) {
    const year = parts[0]
    const month = parts[1]
    const day = parts[2]
    if (year === undefined || month === undefined || day === undefined) return new Date()
    const date = new Date(year, month - 1, day)
    if (date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day) return date
  }
  return new Date()
}

function formatDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function open() {
  selected.value = parseDate(props.modelValue)
  show.value = true
}

function confirm(date: Date | Date[]) {
  const selectedDate = Array.isArray(date) ? date[0] : date
  if (!selectedDate) return
  const value = formatDate(selectedDate)
  emit('update:modelValue', value)
  emit('change', value)
  show.value = false
}

function clear() {
  emit('update:modelValue', '')
  emit('change', '')
  show.value = false
}

watch(() => props.modelValue, (value) => { selected.value = parseDate(value) })
</script>

<style scoped>
.field-action { display: inline-grid; padding: 4px; place-items: center; border: 0; background: transparent; color: var(--bm-muted); font-size: 16px; }
</style>
