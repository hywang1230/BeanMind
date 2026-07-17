<template>
  <van-field
    :model-value="displayValue"
    :label="label"
    :placeholder="placeholder"
    :error-message="error"
    :rules="rules"
    readonly
    is-link
    @click="open"
  />
  <van-popup v-model:show="show" position="bottom" round>
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
}>(), { placeholder: '请选择', error: '', rules: () => [] })
const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'change', value: string): void
}>()

const show = ref(false)
const selectedValues = ref<Array<string | number>>([props.modelValue])
const displayValue = computed(() => props.options.find(option => option.value === props.modelValue)?.text || '')

function open() {
  selectedValues.value = [props.modelValue]
  show.value = true
}

function confirm({ selectedValues: values }: { selectedValues: Array<string | number> }) {
  const value = String(values[0] ?? '')
  emit('update:modelValue', value)
  emit('change', value)
  show.value = false
}

watch(() => props.modelValue, (value) => { selectedValues.value = [value] })
</script>
