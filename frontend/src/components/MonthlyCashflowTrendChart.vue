<template>
  <div class="cashflow-trend-chart" data-testid="cashflow-trend-chart">
    <div class="legend" aria-hidden="true">
      <span class="legend-item income"><i />收入</span>
      <span class="legend-item expense"><i />支出</span>
      <span class="legend-item net"><i />月净收入</span>
    </div>

    <van-empty
      v-if="isAllZero"
      class="empty-state"
      description="近 12 个月暂无收支数据"
      data-testid="cashflow-trend-empty"
    />

    <template v-else>
      <div class="chart-shell">
        <div class="plot-row">
          <div class="y-axis" aria-hidden="true">
            <span class="y-label y-max">{{ formatAxis(rawBounds.max) }}</span>
            <span
              class="y-label y-zero"
              :style="{ top: `${zeroTopPercent}%` }"
            >0</span>
            <span
              v-if="rawBounds.min < 0"
              class="y-label y-min"
            >{{ formatAxis(rawBounds.min) }}</span>
          </div>

          <div class="plot-main">
            <svg
              class="chart-svg"
              :viewBox="`0 0 ${width} ${height}`"
              role="img"
              :aria-label="ariaLabel"
              preserveAspectRatio="none"
            >
              <line
                class="axis-line"
                :x1="pad.left"
                :x2="width - pad.right"
                :y1="zeroY"
                :y2="zeroY"
              />
              <line
                v-if="selectedIndex >= 0"
                class="selection-line"
                :x1="xAt(selectedIndex)"
                :x2="xAt(selectedIndex)"
                :y1="pad.top"
                :y2="height - pad.bottom"
              />
              <polyline class="series income" fill="none" :points="polyline('income')" />
              <polyline class="series expense" fill="none" :points="polyline('expense')" />
              <polyline class="series net" fill="none" :points="polyline('net_income')" />
              <g v-for="(point, index) in points" :key="point.month">
                <circle
                  class="dot income"
                  :class="{ selected: selectedIndex === index }"
                  :cx="xAt(index)"
                  :cy="yAt(point.income)"
                  :r="selectedIndex === index ? 4 : 3"
                />
                <circle
                  class="dot expense"
                  :class="{ selected: selectedIndex === index }"
                  :cx="xAt(index)"
                  :cy="yAt(point.expense)"
                  :r="selectedIndex === index ? 4 : 3"
                />
                <circle
                  class="dot net"
                  :class="{ selected: selectedIndex === index }"
                  :cx="xAt(index)"
                  :cy="yAt(point.net_income)"
                  :r="selectedIndex === index ? 4.5 : 3.5"
                />
              </g>
            </svg>

            <div class="month-hit-layer" role="listbox" :aria-label="`选择月份，共 ${points.length} 个月`">
              <button
                v-for="(point, index) in points"
                :key="point.month"
                type="button"
                class="month-hit"
                role="option"
                :aria-selected="selectedMonth === point.month"
                :data-month="point.month"
                :class="{ active: selectedMonth === point.month }"
                @click="selectMonth(point.month)"
                @focus="selectMonth(point.month)"
                @keydown.left.prevent="moveSelection(-1)"
                @keydown.right.prevent="moveSelection(1)"
                @keydown.home.prevent="selectMonth(points[0]?.month)"
                @keydown.end.prevent="selectMonth(points[points.length - 1]?.month)"
              >
                <span class="month-label">{{ monthLabel(point.month, index) }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="selectedPoint" class="detail-panel" data-testid="cashflow-trend-detail">
        <div class="detail-month">{{ selectedPoint.month }}</div>
        <div class="detail-row income">
          <span>收入</span>
          <strong>{{ formatMoney(selectedPoint.income) }} {{ currency }}</strong>
        </div>
        <div class="detail-row expense">
          <span>支出</span>
          <strong>{{ formatMoney(selectedPoint.expense) }} {{ currency }}</strong>
        </div>
        <div class="detail-row net">
          <span>月净收入</span>
          <strong>{{ formatMoney(selectedPoint.net_income) }} {{ currency }}</strong>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { MonthlyCashflowPoint } from '../api/reports'
import { formatAmountDisplay, isZero } from '../utils/decimal'

const props = withDefaults(defineProps<{
  points: MonthlyCashflowPoint[]
  currency?: string
  title?: string
}>(), {
  currency: 'CNY',
  title: '近 12 个月收支趋势',
})

const selectedMonth = ref('')

const width = 360
const height = 180
const pad = { top: 12, right: 8, bottom: 10, left: 8 }

const points = computed(() => props.points || [])

const numericSeries = computed(() => {
  return points.value.map((point) => ({
    month: point.month,
    income: toFiniteNumber(point.income),
    expense: toFiniteNumber(point.expense),
    net_income: toFiniteNumber(point.net_income),
  }))
})

const isAllZero = computed(() => {
  if (!points.value.length) return true
  return points.value.every(
    (point) => isZero(point.income) && isZero(point.expense) && isZero(point.net_income),
  )
})

/** 有符号平方根压缩，避免极端月份把后续小额压成贴零轴。 */
function compress(value: number): number {
  if (value === 0) return 0
  const sign = value < 0 ? -1 : 1
  return sign * Math.sqrt(Math.abs(value))
}

const rawBounds = computed(() => {
  const values = numericSeries.value.flatMap((point) => [
    point.income,
    point.expense,
    point.net_income,
  ])
  if (!values.length) return { min: -1, max: 1 }
  return {
    min: Math.min(...values, 0),
    max: Math.max(...values, 0),
  }
})

const bounds = computed(() => {
  const values = numericSeries.value.flatMap((point) => [
    point.income,
    point.expense,
    point.net_income,
  ])
  if (!values.length) return { min: -1, max: 1 }
  const compressed = values.map(compress)
  let min = Math.min(...compressed, 0)
  let max = Math.max(...compressed, 0)
  if (min === max) {
    min -= 1
    max += 1
  }
  const padAmount = (max - min) * 0.08
  return { min: min - padAmount, max: max + padAmount }
})

const zeroY = computed(() => yFromValue(0))

const zeroTopPercent = computed(() => {
  const usable = height - pad.top - pad.bottom
  if (usable <= 0) return 50
  return ((zeroY.value - pad.top) / usable) * 100
})

const selectedIndex = computed(() =>
  points.value.findIndex((point) => point.month === selectedMonth.value),
)

const selectedPoint = computed(() =>
  points.value.find((point) => point.month === selectedMonth.value) || null,
)

const ariaLabel = computed(() => {
  if (!selectedPoint.value) return props.title
  return `${props.title}，选中 ${selectedPoint.value.month}：收入 ${selectedPoint.value.income}，支出 ${selectedPoint.value.expense}，月净收入 ${selectedPoint.value.net_income} ${props.currency}`
})

watch(
  () => points.value.map((point) => point.month).join(','),
  () => {
    selectedMonth.value = points.value[points.value.length - 1]?.month || ''
  },
  { immediate: true },
)

function toFiniteNumber(value: string): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function xAt(index: number): number {
  const count = Math.max(points.value.length - 1, 1)
  const usable = width - pad.left - pad.right
  return pad.left + (usable * index) / count
}

function yFromValue(value: number): number {
  const compressed = compress(value)
  const { min, max } = bounds.value
  const usable = height - pad.top - pad.bottom
  const ratio = (compressed - min) / (max - min || 1)
  return pad.top + usable * (1 - ratio)
}

function yAt(raw: string): number {
  return yFromValue(toFiniteNumber(raw))
}

function polyline(key: 'income' | 'expense' | 'net_income'): string {
  return numericSeries.value
    .map((point, index) => `${xAt(index)},${yFromValue(point[key])}`)
    .join(' ')
}

function selectMonth(month?: string) {
  if (!month) return
  selectedMonth.value = month
}

function moveSelection(delta: number) {
  if (!points.value.length) return
  const current = selectedIndex.value
  const next = Math.min(
    points.value.length - 1,
    Math.max(0, (current < 0 ? points.value.length - 1 : current) + delta),
  )
  const target = points.value[next]
  if (target) selectedMonth.value = target.month
}

function monthLabel(month: string, index: number): string {
  const [, mm] = month.split('-')
  if (index === 0 || mm === '01') {
    return month.slice(2)
  }
  return String(Number(mm))
}

function formatMoney(value: string): string {
  return formatAmountDisplay(value, 2)
}

function formatAxis(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 10000) {
    const wan = abs / 10000
    const text = wan >= 10 ? wan.toFixed(0) : wan.toFixed(1).replace(/\.0$/, '')
    return `${sign}${text}万`
  }
  if (abs >= 1000) {
    return `${sign}${(abs / 1000).toFixed(1).replace(/\.0$/, '')}k`
  }
  return `${Math.round(value)}`
}

defineExpose({
  selectedMonth,
  isAllZero,
  selectMonth,
  bounds,
  rawBounds,
  zeroY,
  yFromValue,
})
</script>

<style scoped>
.cashflow-trend-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.legend {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--bm-muted);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-item i {
  width: 10px;
  height: 3px;
  border-radius: 999px;
  background: currentColor;
  display: inline-block;
}
.legend-item.income,
.detail-row.income strong { color: var(--bm-income); }
.legend-item.expense,
.detail-row.expense strong { color: var(--bm-expense); }
.legend-item.net,
.detail-row.net strong { color: var(--bm-net); }
.chart-shell {
  width: 100%;
  background: var(--bm-control);
  border: 1px solid var(--bm-border);
  border-radius: 12px;
  overflow: hidden;
}
.plot-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  align-items: stretch;
}
.y-axis {
  position: relative;
  height: 180px;
  padding: 8px 4px 0 6px;
  color: var(--bm-faint);
  font-size: 10px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.y-label {
  position: absolute;
  left: 4px;
  right: 2px;
  text-align: right;
  white-space: nowrap;
}
.y-max { top: 8px; }
.y-zero {
  transform: translateY(-50%);
}
.y-min { bottom: 8px; }
.plot-main {
  min-width: 0;
}
.chart-svg {
  display: block;
  width: 100%;
  height: 180px;
}
.axis-line {
  stroke: var(--bm-border);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}
.selection-line {
  stroke: var(--bm-primary);
  stroke-width: 1;
  opacity: 0.55;
}
.series {
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.series.income { stroke: var(--bm-income); }
.series.expense { stroke: var(--bm-expense); stroke-dasharray: 5 3; }
.series.net { stroke: var(--bm-net); stroke-width: 2.4; }
.dot.income { fill: var(--bm-income); }
.dot.expense { fill: var(--bm-expense); }
.dot.net { fill: var(--bm-net); stroke: var(--bm-surface); stroke-width: 1; }
.dot.selected {
  stroke: var(--bm-surface);
  stroke-width: 1.5;
}
.month-hit-layer {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid var(--bm-border);
  background: var(--bm-surface);
}
.month-hit {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--bm-muted);
  font-size: 10px;
  line-height: 1.2;
  padding: 8px 0;
  min-height: 36px;
  cursor: pointer;
}
.month-hit.active {
  color: var(--bm-primary);
  font-weight: 700;
  background: color-mix(in srgb, var(--bm-primary-soft) 70%, transparent);
}
.month-label {
  display: block;
  text-align: center;
}
.detail-panel {
  border: 1px solid var(--bm-border);
  border-radius: 12px;
  background: var(--bm-surface);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}
.detail-month {
  font-weight: 700;
  color: var(--bm-text);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--bm-muted);
}
.detail-row strong {
  font-variant-numeric: tabular-nums;
}
.empty-state {
  padding: 18px 0 8px;
}
</style>
