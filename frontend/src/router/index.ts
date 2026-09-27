import { showToast } from 'vant'
import { useTransactionDraftStore } from '../stores/transactionDraft'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    children: [
      { path: 'dashboard', component: () => import('../pages/dashboard/DashboardPage.vue'), meta: { tab: 'dashboard', title: '首页' } },
      { path: 'transactions', component: () => import('../pages/transactions/TransactionsPage.vue'), meta: { tab: 'transactions', title: '流水', keepAlive: true } },
      { path: 'transactions/new', component: () => import('../pages/transactions/AddTransactionPage.vue'), meta: { title: '记一笔' } },
      { path: 'transactions/distribute', component: () => import('../pages/transactions/TransactionDistributePage.vue'), meta: { title: '分配金额' } },
      { path: 'transactions/:id/edit', component: () => import('../pages/transactions/EditTransactionPage.vue'), meta: { title: '编辑交易' } },
      { path: 'transactions/:id', component: () => import('../pages/transactions/TransactionDetailPage.vue'), meta: { title: '交易详情' } },
      { path: 'budgets', component: () => import('../pages/budgets/BudgetsPage.vue'), meta: { tab: 'budgets', title: '预算' } },
      { path: 'reviews/:month', component: () => import('../pages/reports/MonthlyReportPage.vue'), meta: { title: '月度复盘' } },
      { path: 'settings', component: () => import('../pages/settings/SettingsPage.vue'), meta: { tab: 'settings', title: '设置' } },
      { path: 'accounts', component: () => import('../pages/accounts/AccountsPage.vue'), meta: { title: '账户' } },
      { path: 'accounts/:accountName', component: () => import('../pages/accounts/AccountDetailPage.vue'), meta: { title: '账户详情' } },
      { path: 'recurring', component: () => import('../pages/recurring/RecurringPage.vue'), meta: { title: '周期记账' } },
      { path: 'exchange-rates', component: () => import('../pages/exchange-rates/ExchangeRatesPage.vue'), meta: { title: '汇率' } },
      { path: 'currencies', component: () => import('../pages/currencies/CurrenciesPage.vue'), meta: { title: '币种管理' } },
      { path: 'reports', component: () => import('../pages/reports/ReportsPage.vue'), meta: { title: '报表' } },
      { path: 'reports/balance-sheet', component: () => import('../pages/reports/BalanceSheetPage.vue'), meta: { title: '资产负债表' } },
      { path: 'reports/trial-balance', component: () => import('../pages/reports/TrialBalancePage.vue'), meta: { title: '试算表' } },
      { path: 'reports/income-statement', component: () => import('../pages/reports/IncomeStatementPage.vue'), meta: { title: '利润表' } },
      { path: 'reports/account-detail', component: () => import('../pages/reports/AccountDetailPage.vue'), meta: { title: '账户明细' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

// Keep the current draft and deletion context until the write has a known response
// or the user explicitly finishes the read-only verification in the current page.
router.beforeEach(() => {
  const draftStore = useTransactionDraftStore()
  if (draftStore.pendingWrite || draftStore.unconfirmed) {
    showToast(draftStore.pendingWrite ? '正在保存，请等待操作结果' : '操作结果未确认，请先在当前页面核对')
    return false
  }
})

export default router
