<template>
  <van-field
    :model-value="displayValue"
    label="日期范围"
    placeholder="请选择日期范围"
    readonly
    @click="open"
  >
    <template #right-icon>
      <button v-if="startDate || endDate" type="button" class="field-action" aria-label="清空日期范围" @click.stop="clear">
        <van-icon name="cross" />
      </button>
      <van-icon v-else name="arrow" />
    </template>
  </van-field>
  <van-calendar
    v-model:show="show"
    type="range"
    title="选择日期范围"
    :default-date="selected"
    :min-date="minDate"
    :max-date="maxDate"
    allow-same-day
    switch-mode="year-month"
    @confirm="confirm"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  startDate?: string
  endDate?: string
}>(), { startDate: '', endDate: '' })
const emit = defineEmits<{
  (event: 'update:startDate', value: string): void
  (event: 'update:endDate', value: string): void
  (event: 'change', value: { startDate: string; endDate: string }): void
}>()

const show = ref(false)
const minDate = new Date(2000, 0, 1)
const maxDate = new Date(2100, 11, 31)
const selected = ref<Date[] | null>(parseRange())
const displayValue = computed(() => {
  if (props.startDate && props.endDate) return `${props.startDate} 至 ${props.endDate}`
  if (props.startDate) return `自 ${props.startDate}`
  if (props.endDate) return `至 ${props.endDate}`
  return ''
})

function parseDate(value?: string) {
  const parts = value?.split('-').map(Number)
  if (parts?.length !== 3) return null
  const [year, month, day] = parts
  if (year === undefined || month === undefined || day === undefined) return null
  const date = new Date(year, month - 1, day)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null
}

function parseRange() {
  const start = parseDate(props.startDate)
  const end = parseDate(props.endDate)
  if (start && end && end >= start) return [start, end]
  const single = start || end
  return single ? [single, single] : null
}

function formatDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function open() {
  selected.value = parseRange()
  show.value = true
}

function confirm(value: Date | Date[]) {
  if (!Array.isArray(value) || !value[0] || !value[1]) return
  const startDate = formatDate(value[0])
  const endDate = formatDate(value[1])
  emit('update:startDate', startDate)
  emit('update:endDate', endDate)
  emit('change', { startDate, endDate })
  show.value = false
}

function clear() {
  emit('update:startDate', '')
  emit('update:endDate', '')
  emit('change', { startDate: '', endDate: '' })
  show.value = false
}

watch([() => props.startDate, () => props.endDate], () => { selected.value = parseRange() })
</script>

<style scoped>
.field-action { display: inline-grid; padding: 4px; place-items: center; border: 0; background: transparent; color: var(--bm-muted); font-size: 16px; }
</style>
