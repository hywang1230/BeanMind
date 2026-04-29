<template>
  <f7-popup :opened="opened" @popup:closed="onPopupClosed">
    <f7-page>
      <f7-navbar>
        <f7-nav-left>
          <f7-link popup-close>
            <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
            <span></span>
          </f7-link>
        </f7-nav-left>
        <f7-nav-title>选择目标月份</f7-nav-title>
      </f7-navbar>

      <f7-block class="month-picker-block">
        <div class="year-toolbar">
          <f7-button small tonal @click="changeYear(-1)">上一年</f7-button>
          <div class="year-value">{{ currentYear }}年</div>
          <f7-button small tonal @click="changeYear(1)">下一年</f7-button>
        </div>

        <div class="month-grid">
          <button
            v-for="month in months"
            :key="month.value"
            type="button"
            class="month-cell"
            :class="{ selected: month.value === currentMonth }"
            @click="selectMonth(month.value)"
          >
            {{ month.label }}
          </button>
        </div>
      </f7-block>
    </f7-page>
  </f7-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  f7Popup,
  f7Page,
  f7Navbar,
  f7NavLeft,
  f7NavTitle,
  f7Link,
  f7Icon,
  f7Block,
  f7Button,
} from 'framework7-vue'

const props = defineProps<{
  opened: boolean
  value: string
}>()

const emit = defineEmits<{
  (e: 'update:opened', value: boolean): void
  (e: 'select', value: string): void
}>()

const months = [
  { value: '01', label: '1月' },
  { value: '02', label: '2月' },
  { value: '03', label: '3月' },
  { value: '04', label: '4月' },
  { value: '05', label: '5月' },
  { value: '06', label: '6月' },
  { value: '07', label: '7月' },
  { value: '08', label: '8月' },
  { value: '09', label: '9月' },
  { value: '10', label: '10月' },
  { value: '11', label: '11月' },
  { value: '12', label: '12月' },
]

const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(String(new Date().getMonth() + 1).padStart(2, '0'))

function syncFromValue(value: string) {
  const [year, month] = value.split('-')
  if (year && month) {
    currentYear.value = Number(year)
    currentMonth.value = month
  }
}

function changeYear(offset: number) {
  currentYear.value += offset
}

function selectMonth(month: string) {
  currentMonth.value = month
  emit('select', `${currentYear.value}-${month}`)
  emit('update:opened', false)
}

function onPopupClosed() {
  emit('update:opened', false)
}

watch(
  () => props.opened,
  (opened) => {
    if (opened) {
      syncFromValue(props.value)
    }
  }
)
</script>

<style scoped>
:deep(.page) {
  background-color: var(--bg-primary);
}

:deep(.navbar-inner),
:deep(.navbar-bg) {
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.month-picker-block {
  margin: 0;
  padding: 20px 16px 24px;
}

.year-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.year-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.month-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.month-cell {
  border: 0.5px solid var(--separator);
  border-radius: 12px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 500;
  padding: 16px 0;
  transition: all 0.2s ease;
}

.month-cell.selected {
  background: var(--f7-theme-color, #007aff);
  border-color: var(--f7-theme-color, #007aff);
  color: #fff;
}

.month-cell:active {
  transform: scale(0.98);
}
</style>
