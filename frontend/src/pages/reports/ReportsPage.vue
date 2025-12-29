<template>
  <f7-page name="reports">
    <f7-navbar title="财务报表">
      <template #left>
        <f7-link @click="goBack">
          <f7-icon f7="chevron_left"></f7-icon>
        </f7-link>
      </template>
    </f7-navbar>

    <div class="reports-content">
      <!-- 报表入口卡片 -->
      <div class="report-cards">
        <!-- 资产负债表 -->
        <div class="report-card" @click="goToBalanceSheet">
          <div class="report-icon balance-sheet-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="32" height="32">
              <path
                d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
            </svg>
          </div>
          <div class="report-info">
            <h3 class="report-title">资产负债表</h3>
            <p class="report-desc">查看某一时点的资产、负债和权益状况</p>
          </div>
          <div class="report-arrow">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
            </svg>
          </div>
        </div>

        <!-- 利润表 -->
        <div class="report-card" @click="goToIncomeStatement">
          <div class="report-icon income-statement-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="32" height="32">
              <path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z" />
            </svg>
          </div>
          <div class="report-info">
            <h3 class="report-title">利润表</h3>
            <p class="report-desc">查看某一期间的收入、支出和净利润</p>
          </div>
          <div class="report-arrow">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
            </svg>
          </div>
        </div>
      </div>

      <!-- 报表说明 -->
      <div class="report-help">
        <h4 class="help-title">报表说明</h4>
        <div class="help-item">
          <span class="help-label">资产负债表</span>
          <span class="help-text">反映某一特定日期企业的资产、负债和所有者权益的静态报表。会计恒等式：资产 = 负债 + 权益</span>
        </div>
        <div class="help-item">
          <span class="help-label">利润表</span>
          <span class="help-text">反映某一会计期间收入和支出情况的动态报表，用于分析盈利能力。净利润 = 收入 - 支出</span>
        </div>
        <div class="help-item">
          <span class="help-label">多币种支持</span>
          <span class="help-text">所有金额均按账本中记录的汇率折算为人民币显示，同时保留原币种明细</span>
        </div>
      </div>
    </div>
  </f7-page>
</template>

<script setup lang="ts">
import { f7Page, f7Navbar, f7Link, f7Icon } from 'framework7-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

function goBack() {
  router.back()
}

function goToBalanceSheet() {
  router.push('/reports/balance-sheet')
}

function goToIncomeStatement() {
  router.push('/reports/income-statement')
}
</script>

<style scoped>
.reports-content {
  min-height: 100%;
  background: var(--bg-primary);
  padding: 16px;
  transition: background-color 0.3s;
}

.report-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.report-card {
  display: flex;
  align-items: center;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.report-card:active {
  transform: scale(0.98);
  background: var(--bg-tertiary);
}

.report-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 14px;
  flex-shrink: 0;
}

.balance-sheet-icon {
  background: linear-gradient(135deg, #34c759 0%, #30b354 100%);
  color: #fff;
}

.income-statement-icon {
  background: linear-gradient(135deg, #007aff 0%, #0066d6 100%);
  color: #fff;
}

.report-info {
  flex: 1;
  min-width: 0;
}

.report-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.report-desc {
  font-size: 13px;
  color: #8e8e93;
  margin: 0;
  line-height: 1.4;
}

.report-arrow {
  color: #c6c6c8;
  flex-shrink: 0;
  margin-left: 8px;
}

/* 报表说明 */
.report-help {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;
  transition: background-color 0.3s;
}

.help-title {
  font-size: 13px;
  font-weight: 600;
  color: #8e8e93;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px;
}

.help-item {
  padding: 12px 0;
  border-bottom: 0.5px solid var(--separator);
}

.help-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.help-label {
  display: block;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.help-text {
  font-size: 13px;
  color: #8e8e93;
  line-height: 1.5;
}
</style>
