<template>
  <PullToRefresh @refresh="onRefresh">
    <div class="dashboard-page">
      <!-- 顶部标题 -->
      <div class="page-header">
        <h1>首页</h1>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <div class="loading-spinner"></div>
      </div>

      <div v-else class="dashboard-content">
        <!-- 总资产卡片 -->
        <div class="card assets-card">
          <!-- 净资产 - 主要信息 -->
          <div class="net-worth-section">
            <div class="net-worth-label">净资产</div>
            <div class="net-worth-value" :class="{ negative: assetData.net_assets < 0 }">
              {{ assetData.net_assets >= 0 ? '' : '-' }}¥{{ formatNumber(assetData.net_assets) }}
            </div>
          </div>

          <!-- 资产与负债 - 次要信息 -->
          <div class="asset-liability-row">
            <div class="al-item">
              <span class="al-label">资产</span>
              <span class="al-value assets">¥{{ formatNumber(assetData.total_assets) }}</span>
            </div>
            <div class="al-divider"></div>
            <div class="al-item">
              <span class="al-label">负债</span>
              <span class="al-value liabilities">¥{{ formatNumber(assetData.total_liabilities) }}</span>
            </div>
          </div>
        </div>


        <!-- 本月概览 -->
        <div class="card">
          <div class="card-header">本月概览</div>
          <div class="monthly-row">
            <div class="monthly-item">
              <div class="monthly-label">收入</div>
              <div class="monthly-value" :class="monthlyData.income >= 0 ? 'income' : 'expense'">
                {{ monthlyData.income >= 0 ? '+' : '-' }}¥{{ formatNumber(monthlyData.income) }}
              </div>
            </div>
            <div class="monthly-item">
              <div class="monthly-label">支出</div>
              <div class="monthly-value expense">-¥{{ formatNumber(monthlyData.expense) }}</div>
            </div>
            <div class="monthly-item">
              <div class="monthly-label">结余</div>
              <div class="monthly-value" :class="monthlyData.net >= 0 ? 'income' : 'expense'">
                {{ monthlyData.net >= 0 ? '+' : '' }}¥{{ formatNumber(monthlyData.net) }}
              </div>
            </div>
          </div>
        </div>

        <!-- 本月支出 Top 3 -->
        <div class="card">
          <div class="card-header">本月支出 Top 3</div>
          <div class="top-list">
            <div v-for="(item, index) in topCategories" :key="item.category" class="top-item">
              <div class="top-rank">{{ index + 1 }}</div>
              <div class="top-info">
                <div class="top-name">{{ item.category }}</div>
                <div class="top-meta">{{ item.percentage.toFixed(1) }}% · {{ item.count }}笔</div>
              </div>
              <div class="top-amount">¥{{ formatNumber(item.amount) }}</div>
            </div>
            <div v-if="topCategories.length === 0" class="empty-hint">
              暂无支出记录
            </div>
          </div>
        </div>

        <!-- 近 6 个月趋势 -->
        <div class="card">
          <div class="card-header">收支趋势</div>
          <div class="chart-container">
            <apexchart v-if="trendData.length > 0" type="line" height="200" :options="chartOptions"
              :series="chartSeries" />
            <div v-else class="empty-hint">暂无数据</div>
          </div>
        </div>
      </div>
    </div>
  </PullToRefresh>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import VueApexCharts from 'vue3-apexcharts'
import { useStatisticsStore } from '../../stores/statistics'
import { useUIStore } from '../../stores/ui'
import type { AssetOverview, CategoryStatistics, MonthlyTrend } from '../../api/statistics'
import PullToRefresh from '../../components/PullToRefresh.vue'

const apexchart = VueApexCharts
const statisticsStore = useStatisticsStore()

const loading = ref(true)

// 资产数据
const assetData = ref<AssetOverview>({
  net_assets: 0,
  total_assets: 0,
  total_liabilities: 0,
  currency: 'CNY'
})

// 本月数据
const monthlyData = ref({
  income: 0,
  expense: 0,
  net: 0
})

// 支出 Top 3
const topCategories = ref<CategoryStatistics[]>([])

// 月度趋势数据
const trendData = ref<MonthlyTrend[]>([])

// 固定取最近 6 个月数据
const last6MonthsTrend = computed(() => trendData.value.slice(-6))

// 图表配置
const chartOptions = computed(() => {
  const uiStore = useUIStore();
  // 检查是否为暗黑模式 (dark 或 auto 且系统为 dark)
  const isDark = uiStore.themeMode === 'dark' ||
    (uiStore.themeMode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  return {
    chart: {
      id: 'trend-chart',
      toolbar: { show: false },
      background: 'transparent',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      animations: { enabled: true, easing: 'easeinout', speed: 500 },
      // 禁用缩放、选区、平移，只保留查看详情
      zoom: { enabled: false },
      selection: { enabled: false }
    },
    colors: [isDark ? '#30d158' : '#34c759', isDark ? '#ff453a' : '#ff3b30'], // iOS 绿/红
    stroke: { curve: 'smooth' as const, width: 2.5 },
    xaxis: {
      categories: last6MonthsTrend.value.map(item => {
        const [, month] = item.month.split('-')
        return `${parseInt(month || '0')}月`
      }),
      labels: { style: { colors: '#8e8e93', fontSize: '10px' } },
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: {
      labels: {
        formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`,
        style: { colors: '#8e8e93', fontSize: '10px' }
      }
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: { formatter: (v: number) => `${v >= 0 ? '' : '-'}¥${formatNumber(v)}` }
    },
    legend: {
      position: 'top' as const,
      horizontalAlign: 'right' as const,
      fontSize: '11px',
      labels: { colors: '#8e8e93' },
      markers: { size: 6 }
    },
    grid: {
      borderColor: isDark ? '#2c2c2e' : '#e5e5ea',
      strokeDashArray: 0,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { left: 0, right: 0 }
    },
    markers: { size: 3, strokeWidth: 0 }
  }
})

const chartSeries = computed(() => [
  { name: '收入', data: last6MonthsTrend.value.map(item => item.income) },
  { name: '支出', data: last6MonthsTrend.value.map(item => Math.abs(item.expense)) }
])

function formatNumber(num: number | undefined | null): string {
  if (num === undefined || num === null || isNaN(num)) return '0.00'
  return Math.abs(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadDashboardData() {
  loading.value = true
  try {
    // 使用统计缓存 Store（自动处理缓存逻辑）
    const { assets, categories, trend } = await statisticsStore.fetchDashboardData()

    assetData.value = assets || {
      net_assets: 0, total_assets: 0, total_liabilities: 0, currency: 'CNY'
    }

    // 从 trend 数据获取本月概览（最后一个月即为当前月）
    const currentMonthTrend = trend && trend.length > 0 ? trend[trend.length - 1] : null
    monthlyData.value = {
      income: currentMonthTrend?.income || 0,
      expense: Math.abs(currentMonthTrend?.expense || 0),
      net: currentMonthTrend?.net || 0
    }

    topCategories.value = categories || []
    trendData.value = trend || []
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value = false
  }
}

// 下拉刷新处理
async function onRefresh(done: () => void) {
  try {
    // 强制刷新数据（清除缓存）
    statisticsStore.invalidateCache()
    await loadDashboardData()
  } finally {
    done()
  }
}

onMounted(() => { loadDashboardData() })
</script>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background: var(--bg-primary);
  padding: 0 0px 8px;
  /* 确保变量更新能重新渲染 */
  transition: background-color 0.3s;
}

.page-header {
  padding: 12px 0 8px;
  position: sticky;
  top: 0;
  background: var(--bg-primary);
  z-index: 10;
  transition: background-color 0.3s;
}

.page-header h1 {
  font-size: 34px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.4px;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--separator);
  border-top-color: var(--ios-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}


.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}


/* iOS 风格卡片 */
.card {
  background: var(--bg-secondary);
  border-radius: 12px;
  overflow: hidden;
  transition: background-color 0.3s;
}

.card-header {
  font-size: 13px;
  font-weight: 600;
  color: #8e8e93;
  text-transform: uppercase;
  letter-spacing: -0.08px;
  padding: 12px 16px 8px;
}

/* 资产卡片 */
.assets-card {
  padding: 20px 16px;
}

/* 净资产区域 */
.net-worth-section {
  text-align: center;
  margin-bottom: 16px;
}

.net-worth-label {
  font-size: 13px;
  color: #8e8e93;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.net-worth-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--ios-blue);
  letter-spacing: -0.5px;
}

.net-worth-value.negative {
  color: var(--ios-red);
}

/* 资产与负债行 */
.asset-liability-row {
  display: flex;
  justify-content: center;
  align-items: center;
  padding-top: 12px;
  border-top: 0.5px solid var(--separator);
}

.al-item {
  flex: 1;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.al-label {
  font-size: 12px;
  color: #8e8e93;
}

.al-value {
  font-size: 15px;
  font-weight: 600;
}

.al-value.assets {
  color: var(--ios-green);
}

.al-value.liabilities {
  color: var(--ios-orange);
}

.al-divider {
  width: 0.5px;
  height: 28px;
  background: var(--separator);
}

/* 本月概览 */
.monthly-row {
  display: flex;
  padding: 0 16px 16px;
}

.monthly-item {
  flex: 1;
  text-align: center;
}

.monthly-label {
  font-size: 13px;
  color: #8e8e93;
  margin-bottom: 4px;
}

.monthly-value {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
}

.monthly-value.income {
  color: var(--ios-green);
}

.monthly-value.expense {
  color: var(--ios-red);
}

/* Top 列表 */
.top-list {
  padding: 0 16px 8px;
}

.top-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 0.5px solid var(--separator);
}

.top-item:last-child {
  border-bottom: none;
}

.top-rank {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--ios-blue);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.top-item:nth-child(1) .top-rank {
  background: var(--ios-orange);
}

.top-item:nth-child(2) .top-rank {
  background: #8e8e93;
}

.top-item:nth-child(3) .top-rank {
  background: #af7e56;
}

.top-info {
  flex: 1;
}

.top-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.top-meta {
  font-size: 12px;
  color: #8e8e93;
  margin-top: 2px;
}

.top-amount {
  font-size: 15px;
  font-weight: 600;
  color: var(--ios-red);
}

/* 图表容器 */
.chart-container {
  padding: 0 8px 8px;
}

.empty-hint {
  text-align: center;
  padding: 24px 16px;
  font-size: 14px;
  color: #8e8e93;
}
</style>
