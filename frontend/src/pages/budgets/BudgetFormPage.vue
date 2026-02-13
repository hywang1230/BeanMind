<template>
    <f7-page name="budget-form">
        <f7-navbar>
            <f7-nav-left>
                <f7-link @click="goBack">
                    <f7-icon ios="f7:chevron_left" md="material:arrow_back" />
                </f7-link>
            </f7-nav-left>
            <f7-nav-title>{{ isEdit ? '编辑预算' : '创建预算' }}</f7-nav-title>
            <f7-nav-right>
                <f7-link @click="handleSubmit" :class="{ disabled: !canSubmit || submitting }">
                    {{ submitting ? '保存中' : '保存' }}
                </f7-link>
            </f7-nav-right>
        </f7-navbar>

        <!-- 基本信息 -->
        <f7-block-title>基本信息</f7-block-title>
        <f7-list strong-ios dividers-ios inset>
            <f7-list-input label="预算名称" type="text" placeholder="例如: 2025年生活费预算" :value="form.name"
                @input="form.name = $event.target.value" required />

            <f7-list-input label="预算总金额" type="number" placeholder="请输入金额" :value="form.amount"
                @input="form.amount = Number($event.target.value)" min="0" required>
                <template #media>
                    <span class="currency-symbol">¥</span>
                </template>
            </f7-list-input>
        </f7-list>

        <!-- 日期范围 -->
        <f7-block-title>日期范围</f7-block-title>
        <f7-list strong-ios dividers-ios inset>
            <f7-list-input label="开始日期" type="datepicker" :value="[form.start_date]" readonly
                :calendar-params="{ dateFormat: 'yyyy-mm-dd', closeOnSelect: true }"
                @calendar:change="onCalendarStartChange" />
            <f7-list-input label="结束日期" type="datepicker" :value="[form.end_date]" readonly
                :calendar-params="{ dateFormat: 'yyyy-mm-dd', closeOnSelect: true }"
                @calendar:change="onCalendarEndChange" />
        </f7-list>

        <!-- 循环预算设置 -->
        <f7-block-title>循环预算</f7-block-title>
        <f7-list strong-ios dividers-ios inset>
            <f7-list-input label="循环类型" type="select" :value="form.cycle_type"
                @change="handleCycleTypeChange($event.target.value)">
                <option value="NONE">不循环</option>
                <option value="MONTHLY">按月循环</option>
                <option value="YEARLY">按年循环</option>
            </f7-list-input>

            <f7-list-item v-if="form.cycle_type !== 'NONE'" title="启用预算延续">
                <template #after>
                    <f7-toggle :checked="form.carry_over_enabled" @toggle:change="form.carry_over_enabled = $event" />
                </template>
            </f7-list-item>

            <f7-block-footer v-if="form.cycle_type !== 'NONE'" class="cycle-hint">
                <p v-if="form.cycle_type === 'MONTHLY'">
                    <f7-icon ios="f7:info_circle" md="material:info" />
                    按月循环：系统将在预算时间范围内按月生成预算周期。
                </p>
                <p v-else-if="form.cycle_type === 'YEARLY'">
                    <f7-icon ios="f7:info_circle" md="material:info" />
                    按年循环：系统将在预算时间范围内按年生成预算周期。
                </p>
                <p v-if="form.carry_over_enabled">
                    <f7-icon ios="f7:checkmark_circle" md="material:check_circle" />
                    启用延续后，上个周期的剩余预算（正或负）将自动带入下个周期。
                </p>
            </f7-block-footer>
        </f7-list>

        <!-- 选择支出账户 -->
        <f7-block-title>
            选择包含的账户
            <span class="selected-count" v-if="selectedAccountsCount > 0">
                (已选 {{ selectedAccountsCount }} 个)
            </span>
        </f7-block-title>

        <f7-block class="account-tree-container">
            <f7-treeview>
                <account-tree-item v-for="account in expenseAccounts" :key="account.name" :account="account"
                    :selected-accounts="form.selected_accounts" @toggle="toggleAccount" />
            </f7-treeview>
        </f7-block>

        <!-- 错误提示 -->
        <f7-block v-if="error" class="error-block">
            <p>{{ error }}</p>
        </f7-block>
    </f7-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { budgetsApi, type PeriodType, type CycleType } from '../../api/budgets'
import { accountsApi, type Account } from '../../api/accounts'
import { f7, f7TreeviewItem, f7Treeview, f7Checkbox } from 'framework7-vue'

// -------------------------------------------------------------------------
// 内部组件：AccountTreeItem (递归组件)
// -------------------------------------------------------------------------
const AccountTreeItem = defineComponent({
    name: 'AccountTreeItem',
    props: {
        account: {
            type: Object as () => Account,
            required: true
        },
        selectedAccounts: {
            type: Array as () => string[],
            required: true
        }
    },
    emits: ['toggle'],
    setup(props, { emit }) {
        const isSelected = computed(() => props.selectedAccounts.includes(props.account.name))

        // 简化账户名称显示（只显示最后一部分）
        const displayName = computed(() => {
            const parts = props.account.name.split(':')
            return parts[parts.length - 1]
        })

        const hasChildren = computed(() => props.account.children && props.account.children.length > 0)

        const handleCheck = (e: Event) => {
            // 阻止冒泡，避免触发折叠
            e.stopPropagation()
            emit('toggle', props.account.name)
        }

        return () => h(f7TreeviewItem, {
            label: displayName.value,
            selectable: false, // 禁用默认的选择行为，我们自定义 checkbox
            toggleable: hasChildren.value, // 有子节点才可折叠
        }, {
            'media': () => h(f7Checkbox, {
                checked: isSelected.value,
                onChange: handleCheck,
                style: { marginRight: '8px' }
            }),
            'children': () => hasChildren.value
                ? props.account.children!.map(child => h(AccountTreeItem, {
                    account: child,
                    selectedAccounts: props.selectedAccounts,
                    onToggle: (name: string) => emit('toggle', name)
                }))
                : null
        })
    }
})


// -------------------------------------------------------------------------
// 主逻辑
// -------------------------------------------------------------------------
const router = useRouter()
const route = useRoute()

const isEdit = computed(() => !!route.params.id)
const submitting = ref(false)
const error = ref('')
const loadingAccounts = ref(false)
const allAccounts = ref<Account[]>([])

// 账户节点类型（带子账户）
interface AccountNode extends Account {
    children: AccountNode[]
    isLeaf: boolean
}

const form = ref({
    name: '',
    amount: undefined as number | undefined,
    period_type: 'CUSTOM' as PeriodType,  // 默认使用CUSTOM，日期完全自定义
    start_date: '',
    end_date: '',
    selected_accounts: [] as string[],
    // 循环预算相关字段
    cycle_type: 'NONE' as CycleType,
    carry_over_enabled: false
})

// 筛选出支出类账户树（只保留 Expenses 开头的账户树）
const expenseAccounts = computed(() => {
    // allAccounts现在是树的根节点列表
    const root = allAccounts.value.find(a => a.name === 'Expenses' || a.account_type === 'Expenses')
    if (root) {
        return root.children || []
    }
    return []
})

const selectedAccountsCount = computed(() => form.value.selected_accounts.length)

const canSubmit = computed(() => {
    const basicValid =
        form.value.name.trim() !== '' &&
        (form.value.amount !== undefined && form.value.amount > 0) &&
        form.value.start_date !== '' &&
        form.value.end_date !== '' &&
        form.value.selected_accounts.length > 0

    return basicValid
})

function toggleAccount(accountName: string) {
    const idx = form.value.selected_accounts.indexOf(accountName)
    if (idx >= 0) {
        form.value.selected_accounts.splice(idx, 1)
    } else {
        form.value.selected_accounts.push(accountName)
    }
}

// 构建账户树
function buildAccountTree(accounts: Account[]): AccountNode[] {
    const accountMap = new Map<string, AccountNode>()
    const rootNodes: AccountNode[] = []

    // 辅助函数:确保节点存在,如果不存在则创建虚拟节点
    function ensureNode(name: string, accountType: string): AccountNode {
        if (!accountMap.has(name)) {
            accountMap.set(name, {
                name,
                account_type: accountType as any,
                currencies: [],
                children: [],
                isLeaf: true
            })
        }
        return accountMap.get(name)!
    }

    // 首先创建所有实际账户节点
    accounts.forEach(acc => {
        const node = ensureNode(acc.name, acc.account_type)
        node.currencies = acc.currencies
    })

    // 为每个账户创建完整的祖先路径
    accounts.forEach(acc => {
        const parts = acc.name.split(':')
        let currentPath = ''

        for (let i = 0; i < parts.length - 1; i++) {
            currentPath = currentPath ? `${currentPath}:${parts[i]!}` : parts[i]!
            ensureNode(currentPath, acc.account_type)
        }
    })

    // 建立父子关系
    accountMap.forEach((node, name) => {
        const parts = name.split(':')
        if (parts.length > 1) {
            const parentName = parts.slice(0, -1).join(':')
            const parent = accountMap.get(parentName)
            if (parent) {
                // 检查是否已经添加过
                if (!parent.children.find(c => c.name === name)) {
                    parent.children.push(node)
                }
                parent.isLeaf = false
            }
        }
    })

    // 找出根节点(只有一级的账户)
    accountMap.forEach((node, name) => {
        const parts = name.split(':')
        if (parts.length === 1) {
            rootNodes.push(node)
        }
    })

    // 对子账户排序
    function sortChildren(node: AccountNode) {
        node.children.sort((a, b) => a.name.localeCompare(b.name))
        node.children.forEach(sortChildren)
    }
    rootNodes.forEach(sortChildren)
    rootNodes.sort((a, b) => a.name.localeCompare(b.name))

    return rootNodes
}

async function loadAccounts() {
    loadingAccounts.value = true
    try {
        const accounts = await accountsApi.getAccounts()
        allAccounts.value = buildAccountTree(accounts)
    } catch (err) {
        console.error('Failed to load accounts:', err)
        f7.toast.create({
            text: '加载账户失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    } finally {
        loadingAccounts.value = false
    }
}

function initializeForm() {
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth()

    const startDate = new Date(year, month, 1)
    const endDate = new Date(year, month + 1, 0)

    form.value.start_date = formatDateForInput(startDate)
    form.value.end_date = formatDateForInput(endDate)
    form.value.name = `${year}年${month + 1}月预算`
}

function formatDateForInput(date: Date): string {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}


function handleCycleTypeChange(type: CycleType) {
    form.value.cycle_type = type
    // 如果切换到不循环，清空延续设置
    if (type === 'NONE') {
        form.value.carry_over_enabled = false
    }
}

function handleStartDateChange(dateStr: string) {
    form.value.start_date = dateStr
    // 不再自动计算结束日期
}

function onCalendarStartChange(val: any) {
    if (val && val[0]) {
        const date = val[0] instanceof Date ? val[0] : new Date(val[0])
        handleStartDateChange(formatDateForInput(date))
    }
}

function onCalendarEndChange(val: any) {
    if (val && val[0]) {
        const date = val[0] instanceof Date ? val[0] : new Date(val[0])
        form.value.end_date = formatDateForInput(date)
    }
}


async function loadBudget() {
    const budgetId = route.params.id as string
    if (!budgetId) return

    try {
        const budget = await budgetsApi.getBudget(budgetId)
        form.value.name = budget.name
        form.value.amount = budget.amount ?? budget.total_budget
        form.value.period_type = budget.period_type
        form.value.start_date = budget.start_date
        form.value.end_date = budget.end_date || ''
        form.value.selected_accounts = budget.items.map(item => item.account_pattern)
        // 循环预算相关字段
        form.value.cycle_type = budget.cycle_type || 'NONE'
        form.value.carry_over_enabled = budget.carry_over_enabled || false
    } catch (err) {
        console.error('Failed to load budget:', err)
        f7.toast.create({
            text: '加载预算失败',
            position: 'center',
            closeTimeout: 2000
        }).open()
    }
}

async function handleSubmit() {
    if (!canSubmit.value || submitting.value) return

    submitting.value = true
    error.value = ''

    try {
        const data: any = {
            name: form.value.name,
            amount: form.value.amount!,
            period_type: form.value.period_type,
            start_date: form.value.start_date,
            end_date: form.value.end_date || undefined,
            cycle_type: form.value.cycle_type,
            carry_over_enabled: form.value.carry_over_enabled,
            items: form.value.selected_accounts.map(pattern => ({
                account_pattern: pattern,
                amount: 0, // 后端已改为忽略此值
                currency: 'CNY'
            }))
        }

        if (isEdit.value) {
            await budgetsApi.updateBudget(route.params.id as string, data)
            f7.toast.create({
                text: '预算已更新',
                position: 'center',
                closeTimeout: 2000
            }).open()
            router.replace(`/budgets/${route.params.id}`)
        } else {
            const budget = await budgetsApi.createBudget(data)
            f7.toast.create({
                text: '预算已创建',
                position: 'center',
                closeTimeout: 2000
            }).open()
            router.replace(`/budgets/${budget.id}`)
        }
    } catch (err: any) {
        error.value = err.message || '保存失败，请重试'
    } finally {
        submitting.value = false
    }
}

function goBack() {
    router.back()
}

onMounted(async () => {
    await loadAccounts()
    if (isEdit.value) {
        loadBudget()
    } else {
        initializeForm()
    }
})
</script>

<style scoped>
.currency-symbol {
    color: var(--text-secondary);
    font-size: 16px;
    margin-right: 4px;
}

.account-tree-container {
    height: 400px;
    overflow-y: auto;
    border: 1px solid var(--separator);
    border-radius: 8px;
    background: var(--bg-secondary);
    padding: 0;
}

.selected-count {
    color: var(--ios-blue);
    font-weight: normal;
    font-size: 14px;
    margin-left: 8px;
}

.error-block {
    background: rgba(255, 59, 48, 0.12);
    color: var(--ios-red);
    padding: 12px 16px;
    border-radius: 8px;
    margin: 16px;
}

.error-block p {
    margin: 0;
    font-size: 14px;
}

.disabled {
    opacity: 0.5;
    pointer-events: none;
}

.cycle-hint {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
}

.cycle-hint p {
    margin: 8px 0;
    display: flex;
    align-items: flex-start;
    gap: 6px;
}

.cycle-hint .icon {
    flex-shrink: 0;
    margin-top: 2px;
}

:root {
    --text-primary: #1c1c1e;
    --text-secondary: #8e8e93;
    --bg-primary: #f2f2f7;
    --bg-secondary: #ffffff;
    --separator: rgba(60, 60, 67, 0.12);
    --ios-blue: #007aff;
    --ios-red: #ff3b30;
}

@media (prefers-color-scheme: dark) {
    :root {
        --text-primary: #ffffff;
        --text-secondary: #98989d;
        --bg-primary: #000000;
        --bg-secondary: #1c1c1e;
        --separator: rgba(84, 84, 88, 0.65);
    }
}
</style>
