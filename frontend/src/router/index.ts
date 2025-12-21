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
        redirect: '/dashboard'
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('../pages/dashboard/DashboardPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions',
        name: 'Transactions',
        component: () => import('../pages/transactions/TransactionsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions/add',
        name: 'AddTransaction',
        component: () => import('../pages/transactions/AddTransactionPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('../pages/accounts/AccountsPage.vue'),
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
        path: '/settings',
        name: 'Settings',
        component: () => import('../pages/settings/SettingsPage.vue'),
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
            return '/dashboard'
        }
        return true
    }

    // 其他模式下的认证检查
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        return '/login'
    } else if (to.path === '/login' && authStore.isAuthenticated) {
        return '/dashboard'
    }

    return true
})

export default router
