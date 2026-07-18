<template>
  <van-field
    :model-value="displayValue"
    :label="label"
    :placeholder="placeholder"
    :error-message="error"
    :rules="rules"
    readonly
    @click="open"
  >
    <template #right-icon>
      <button v-if="clearable && modelValue" type="button" class="field-action" :aria-label="`清空${label}`" @click.stop="clear">
        <van-icon name="cross" />
      </button>
      <van-icon v-else name="arrow" />
    </template>
  </van-field>
  <van-popup v-model:show="show" position="bottom" round teleport="body">
    <van-picker
      v-model="selectedValues"
      :title="`选择${label}`"
      :columns="options"
      @confirm="confirm"
      @cancel="show = false"
    />
  </van-popup>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  label: string
  options: Array<{ text: string; value: string }>
  placeholder?: string
  error?: string
  rules?: Array<Record<string, unknown>>
  clearable?: boolean
}>(), { placeholder: '请选择', error: '', rules: () => [], clearable: false })
const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
}>()

const show = ref(false)
const selectedValues = ref<Array<string | number>>([props.modelValue])
const displayValue = computed(() => props.options.find(option => option.value === props.modelValue)?.text || '')

function open() {
  if (!props.options.length) return
  const current = props.options.some((option) => option.value === props.modelValue)
    ? props.modelValue
    : props.options[0]?.value || ''
  selectedValues.value = [current]
  show.value = true
}

function confirm({ selectedValues: values }: { selectedValues: Array<string | number> }) {
  const value = String(values[0] ?? '')
  emit('update:modelValue', value)
  emit('change', value)
  show.value = false
}

function clear() {
  emit('update:modelValue', '')
  emit('change', '')
  show.value = false
}

watch(() => props.modelValue, (value) => { selectedValues.value = [value] })
</script>

<style scoped>
.field-action { display: inline-grid; padding: 4px; place-items: center; border: 0; background: transparent; color: var(--bm-muted); font-size: 16px; }
</style>
