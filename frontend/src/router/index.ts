import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('../pages/auth/LoginPage.vue'),
        meta: { requiresAuth: false }
    },
    {
        path: '/',
        name: 'Main',
        component: () => import('../layouts/MainLayout.vue'),
        meta: { requiresAuth: true },
        alias: ['/dashboard', '/transactions', '/ai', '/settings']
    },
    {
        path: '/reports',
        name: 'Reports',
        component: () => import('../pages/reports/ReportsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/reports/balance-sheet',
        name: 'BalanceSheet',
        component: () => import('../pages/reports/BalanceSheetPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/reports/income-statement',
        name: 'IncomeStatement',
        component: () => import('../pages/reports/IncomeStatementPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/reports/account-detail',
        name: 'AccountDetail',
        component: () => import('../pages/reports/AccountDetailPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions/add',
        name: 'AddTransaction',
        component: () => import('../pages/transactions/AddTransactionPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions/distribute',
        name: 'TransactionDistribute',
        component: () => import('../pages/transactions/TransactionDistributePage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions/:id/edit',
        name: 'EditTransaction',
        component: () => import('../pages/transactions/EditTransactionPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions/:id',
        name: 'TransactionDetail',
        component: () => import('../pages/transactions/TransactionDetailPage.vue'),
        meta: { requiresAuth: true }
    },
    // 保留这些页面在主布局外(如果需要单独访问)
    {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('../pages/accounts/AccountsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/accounts/:accountName',
        name: 'AccountManagementDetail',
        component: () => import('../pages/accounts/AccountDetailPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/budgets',
        name: 'Budgets',
        component: () => import('../pages/budgets/BudgetsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/recurring',
        name: 'Recurring',
        component: () => import('../pages/recurring/RecurringPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/recurring/rules',
        name: 'RecurringRules',
        component: () => import('../pages/recurring/RecurringRulesPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/recurring/add',
        name: 'AddRecurringRule',
        component: () => import('../pages/recurring/RecurringRuleFormPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/recurring/:id/edit',
        name: 'EditRecurringRule',
        component: () => import('../pages/recurring/RecurringRuleFormPage.vue'),
        meta: { requiresAuth: true }
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫
router.beforeEach(async (to) => {
    // 延迟导入 authStore 以避免循环依赖
    const { useAuthStore } = await import('../stores/auth')
    const authStore = useAuthStore()

    // 等待配置加载完成
    let retries = 0
    while (!authStore.configLoaded && retries < 50) {
        await new Promise(resolve => setTimeout(resolve, 100))
        retries++
    }

    // 如果是 none 模式，不需要认证
    if (authStore.authMode === 'none') {
        // 如果访问登录页，重定向到首页
        if (to.path === '/login') {
            return '/'
        }
        return true
    }

    // 其他模式下的认证检查
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        return '/login'
    } else if (to.path === '/login' && authStore.isAuthenticated) {
        return '/'
    }

    return true
})

export default router
