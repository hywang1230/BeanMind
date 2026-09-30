<template>
  <van-field v-if="label" :model-value="modelValue" :label="label" readonly is-link @click="open" />
  <van-button v-else class="month-picker-trigger" plain round icon="calendar-o" @click="open">
    {{ modelValue }}
    <van-icon name="arrow" />
  </van-button>
  <van-popup v-model:show="show" position="bottom" round teleport="body">
    <van-date-picker
      v-model="selected"
      title="选择月份"
      :columns-type="['year', 'month']"
      :min-date="minDate"
      :max-date="maxDate"
      @confirm="confirm"
      @cancel="show = false"
    />
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: string; label?: string }>()
const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
}>()
const show = ref(false)
const minDate = new Date(2000, 0, 1)
const maxDate = new Date(2100, 11, 31)
const selected = ref<string[]>(parts(props.modelValue))

function parts(value: string) {
  const [year, month] = value.split('-')
  return [year || String(new Date().getFullYear()), month || String(new Date().getMonth() + 1).padStart(2, '0')]
}

function open() {
  selected.value = parts(props.modelValue)
  show.value = true
}

function confirm() {
  const value = `${selected.value[0]}-${selected.value[1]}`
  emit('update:modelValue', value)
  emit('change', value)
  show.value = false
}

watch(() => props.modelValue, (value) => { selected.value = parts(value) })
</script>

<style scoped>
.month-picker-trigger { min-width: 112px; height: 40px; padding: 0 13px; border-color: var(--bm-border); color: var(--bm-text); }
.month-picker-trigger :deep(.van-button__content) { gap: 6px; }
.month-picker-trigger :deep(.van-button__icon), .month-picker-trigger :deep(.van-icon-arrow) { color: var(--bm-muted); }
</style>
