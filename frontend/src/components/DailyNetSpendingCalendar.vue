<template>
  <div class="daily-net-calendar" data-testid="daily-net-calendar">
    <van-empty
      v-if="isEmptyMonth"
      class="empty-state"
      description="本月暂无收支活动"
      data-testid="daily-net-calendar-empty"
    />

    <template v-else>
      <div class="weekday-row" aria-hidden="true">
        <span v-for="label in weekdayLabels" :key="label">{{ label }}</span>
      </div>

      <div
        class="day-grid"
        role="listbox"
        :aria-label="`选择日期，共 ${days.length} 天`"
        data-testid="daily-net-calendar-grid"
      >
        <span
          v-for="n in leadingPlaceholders"
          :key="`pad-${n}`"
          class="day-cell placeholder"
          aria-hidden="true"
        />
        <button
          v-for="day in days"
          :key="day.date"
          type="button"
          class="day-cell"
          role="option"
          :data-date="day.date"
          :aria-label="dayAriaLabel(day)"
          :aria-selected="selectedDate === day.date"
          :class="dayCellClass(day)"
          :style="dayCellStyle(day)"
          @click="selectDate(day.date)"
          @focus="selectDate(day.date)"
          @keydown.left.prevent="moveSelection(-1)"
          @keydown.right.prevent="moveSelection(1)"
          @keydown.up.prevent="moveSelection(-7)"
          @keydown.down.prevent="moveSelection(7)"
          @keydown.home.prevent="selectDate(days[0]?.date)"
          @keydown.end.prevent="selectDate(days[days.length - 1]?.date)"
        >
          <span class="day-num">{{ dayNumber(day.date) }}</span>
          <span class="day-amount" :class="amountTone(day)">
            {{ compactAmount(day) }}
          </span>
        </button>
      </div>

      <div
        v-if="selectedDay"
        class="detail-panel"
        data-testid="daily-net-calendar-detail"
      >
        <div class="detail-date">{{ selectedDay.date }}</div>
        <div class="detail-row income">
          <span>收入</span>
          <strong>{{ formatMoney(selectedDay.income) }} {{ currency }}</strong>
        </div>
        <div class="detail-row expense">
          <span>支出</span>
          <strong>{{ formatMoney(selectedDay.expense) }} {{ currency }}</strong>
        </div>
        <div class="detail-row net">
          <span>净结余</span>
          <strong :class="amountTone(selectedDay)">
            {{ formatMoney(selectedDay.net_spending) }} {{ currency }}
          </strong>
        </div>
        <div
          v-if="selectedMissingCurrencies.length"
          class="detail-missing"
          data-testid="daily-net-calendar-missing-day"
        >
          当日缺少汇率：{{ selectedMissingCurrencies.join('、') }}，结果不完整
        </div>
        <div
          v-else-if="selectedDay.has_activity && isZero(selectedDay.net_spending)"
          class="detail-note"
          data-testid="daily-net-calendar-zero-activity"
        >
          当日有收支分录，但合计恰好为零
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DailyNetSpendingDay, MissingExchangeRateDay } from '../api/reports'
import {
  absAmount,
  compareAmount,
  formatAmountDisplay,
  isPositive,
  isZero,
} from '../utils/decimal'

const props = withDefaults(defineProps<{
  days: DailyNetSpendingDay[]
  currency?: string
  month: string
  missingExchangeRates?: MissingExchangeRateDay[]
}>(), {
  currency: 'CNY',
  missingExchangeRates: () => [],
})

const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日']
const selectedDate = ref<string | null>(null)

const isEmptyMonth = computed(() => props.days.length > 0 && props.days.every((day) => !day.has_activity))

const leadingPlaceholders = computed(() => {
  const first = props.days[0]?.date
  if (!first) return 0
  const parts = first.split('-').map(Number)
  const date = new Date(parts[0]!, parts[1]! - 1, parts[2])
  // Monday-first: Sun=0 -> 6
  return (date.getDay() + 6) % 7
})

const intensityBounds = computed(() => {
  let maxPositive = '0'
  let maxNegativeAbs = '0'
  for (const day of props.days) {
    if (!day.has_activity || isZero(day.net_spending)) continue
    if (isPositive(day.net_spending)) {
      if (compareAmount(day.net_spending, maxPositive) > 0) maxPositive = day.net_spending
    } else {
      const abs = absAmount(day.net_spending)
      if (compareAmount(abs, maxNegativeAbs) > 0) maxNegativeAbs = abs
    }
  }
  return { maxPositive, maxNegativeAbs }
})

const selectedDay = computed(() => props.days.find((day) => day.date === selectedDate.value) || null)

const selectedMissingCurrencies = computed(() => {
  if (!selectedDate.value) return [] as string[]
  const hit = props.missingExchangeRates.find((item) => item.date === selectedDate.value)
  return hit?.currencies || []
})

function todayIso(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function defaultSelectedDate(days: DailyNetSpendingDay[], month: string): string | null {
  if (!days.length || days.every((day) => !day.has_activity)) return null
  const today = todayIso()
  if (today.startsWith(`${month}-`) && days.some((day) => day.date === today)) return today
  for (let i = days.length - 1; i >= 0; i -= 1) {
    if (days[i]!.has_activity) return days[i]!.date
  }
  return null
}

function selectDate(date?: string) {
  if (!date) return
  selectedDate.value = date
}

function moveSelection(step: number) {
  if (!props.days.length) return
  const current = selectedDate.value || props.days[0]!.date
  const index = props.days.findIndex((day) => day.date === current)
  if (index < 0) {
    selectDate(props.days[0]!.date)
    return
  }
  const next = Math.min(props.days.length - 1, Math.max(0, index + step))
  selectDate(props.days[next]!.date)
}

function dayNumber(date: string): string {
  return String(Number(date.slice(-2)))
}

function formatMoney(value: string): string {
  return formatAmountDisplay(value, 2)
}

function compactAmount(day: DailyNetSpendingDay): string {
  if (!day.has_activity) return ''
  if (isZero(day.net_spending)) return '0'
  const abs = absAmount(day.net_spending)
  // 大额用整数紧凑显示，小额保留两位
  const digits = compareAmount(abs, '100') >= 0 ? 0 : 2
  const body = formatAmountDisplay(abs, digits)
  return isPositive(day.net_spending) ? body : `-${body}`
}

function amountTone(day: DailyNetSpendingDay): string {
  if (!day.has_activity || isZero(day.net_spending)) return 'neutral'
  // 收入为正、支出为负：正净收支用收入色，负净收支用支出色
  return isPositive(day.net_spending) ? 'income' : 'expense'
}

function intensityPercent(day: DailyNetSpendingDay): number {
  if (!day.has_activity || isZero(day.net_spending)) return 0
  const { maxPositive, maxNegativeAbs } = intensityBounds.value
  let ratio = 0
  if (isPositive(day.net_spending)) {
    if (isZero(maxPositive)) return 0
    ratio = Number(absAmount(day.net_spending)) / Number(maxPositive)
  } else {
    if (isZero(maxNegativeAbs)) return 0
    ratio = Number(absAmount(day.net_spending)) / Number(maxNegativeAbs)
  }
  if (!Number.isFinite(ratio) || ratio <= 0) return 0
  // 平方根压缩极端值
  const compressed = Math.sqrt(Math.min(1, Math.max(0, ratio)))
  // 映射到 18%~82% 的主题色占比，避免过淡/过饱和
  return Math.round(18 + compressed * 64)
}

function dayCellClass(day: DailyNetSpendingDay): Record<string, boolean> {
  return {
    active: selectedDate.value === day.date,
    inactive: !day.has_activity,
    zero: day.has_activity && isZero(day.net_spending),
    // 负净收支=支出日，正净收支=结余日
    expense: day.has_activity && !isPositive(day.net_spending) && !isZero(day.net_spending),
    income: day.has_activity && isPositive(day.net_spending),
  }
}

function dayCellStyle(day: DailyNetSpendingDay): Record<string, string> {
  const percent = intensityPercent(day)
  if (percent <= 0) {
    return {
      background: 'var(--bm-surface-2, var(--bm-surface))',
    }
  }
  const token = isPositive(day.net_spending) ? 'var(--bm-income)' : 'var(--bm-expense)'
  return {
    background: `color-mix(in srgb, ${token} ${percent}%, transparent)`,
  }
}

function dayAriaLabel(day: DailyNetSpendingDay): string {
  const status = day.has_activity ? '有活动' : '无活动'
  return `${day.date}，收入 ${formatMoney(day.income)}，支出 ${formatMoney(day.expense)}，净结余 ${formatMoney(day.net_spending)}，${status}`
}

// 暴露给测试使用的内部计算
defineExpose({
  intensityPercent,
  intensityBounds,
  selectedDate,
  defaultSelectedDate,
})

watch(
  () => [props.month, props.days] as const,
  () => {
    selectedDate.value = defaultSelectedDate(props.days, props.month)
  },
  { immediate: true, deep: true },
)
</script>

<style scoped>
.daily-net-calendar {
  display: grid;
  gap: 10px;
}


.weekday-row,
.day-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}

.weekday-row {
  color: var(--bm-muted);
  font-size: 12px;
  text-align: center;
}

.day-cell {
  min-height: 54px;
  border: 1px solid var(--bm-border);
  border-radius: 10px;
  background: var(--bm-surface);
  color: inherit;
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  cursor: pointer;
}

.day-cell.placeholder {
  visibility: hidden;
  pointer-events: none;
  border: none;
  background: transparent;
}

.day-cell.inactive {
  opacity: 0.72;
}

.day-cell.active {
  border-color: var(--bm-primary, #1989fa);
  box-shadow: 0 0 0 1px var(--bm-primary, #1989fa);
}

.day-num {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.1;
}

.day-amount {
  font-size: 10px;
  line-height: 1.1;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.day-amount.expense,
.detail-row.expense strong,
.detail-row.net .expense,
.expense {
  color: var(--bm-expense);
}

.day-amount.income,
.detail-row.income strong,
.detail-row.net .income,
.income {
  color: var(--bm-income);
}

.day-amount.neutral,
.neutral {
  color: var(--bm-muted);
}

.detail-panel {
  border: 1px solid var(--bm-border);
  border-radius: 12px;
  background: var(--bm-surface);
  padding: 12px;
  display: grid;
  gap: 8px;
}

.detail-date {
  font-weight: 600;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.detail-missing {
  color: var(--bm-warn, #ed6a0c);
  font-size: 12px;
}

.detail-note {
  color: var(--bm-muted);
  font-size: 12px;
}

.empty-state {
  padding: 8px 0 4px;
}
</style>
