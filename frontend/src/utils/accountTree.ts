import type { Account } from '../api/accounts'

export type AccountTreeNode = {
  account: Account
  name: string
  label: string
  parentPath: string
  level: number
  selectable: boolean
  children: AccountTreeNode[]
}

export type VisibleAccountNode = AccountTreeNode & { hasChildren: boolean }

type MutableAccountTreeNode = Omit<AccountTreeNode, 'children'> & { children: MutableAccountTreeNode[] }

export function accountLeafLabel(name: string): string {
  const parts = name.split(':').filter(Boolean)
  return parts[parts.length - 1] || name
}

export function buildAccountTree(accounts: Account[]): AccountTreeNode[] {
  const accountMap = new Map<string, Account>()
  collectAccounts(accounts, accountMap)

  const roots: MutableAccountTreeNode[] = []
  const nodeMap = new Map<string, MutableAccountTreeNode>()

  for (const account of accountMap.values()) {
    const parts = account.name.split(':').filter(Boolean)
    if (!parts.length) continue
    for (let index = 0; index < parts.length; index += 1) {
      const name = parts.slice(0, index + 1).join(':')
      const existing = nodeMap.get(name)
      if (existing) {
        const exactAccount = accountMap.get(name)
        if (exactAccount) {
          existing.account = exactAccount
          existing.selectable = true
        }
        continue
      }

      const exactAccount = accountMap.get(name)
      const node: MutableAccountTreeNode = {
        account: exactAccount || syntheticAccount(name),
        name,
        label: parts[index] || accountLeafLabel(name),
        parentPath: parts.slice(0, index).join(':'),
        level: index,
        selectable: Boolean(exactAccount),
        children: [],
      }
      nodeMap.set(name, node)
      if (index === 0) {
        roots.push(node)
      } else {
        const parentName = parts.slice(0, index).join(':')
        const parent = nodeMap.get(parentName)
        parent?.children.push(node)
      }
    }
  }

  return roots.map(stripMutableFields)
}

function collectAccounts(accounts: Account[], result: Map<string, Account>) {
  for (const account of accounts) {
    if (!result.has(account.name)) result.set(account.name, account)
    collectAccounts(account.children || [], result)
  }
}

function syntheticAccount(name: string): Account {
  const accountType = name.split(':')[0] as Account['account_type']
  return { name, account_type: accountType, currencies: [], children: [] }
}

function stripMutableFields(node: MutableAccountTreeNode): AccountTreeNode {
  return {
    account: node.account,
    name: node.name,
    label: node.label,
    parentPath: node.parentPath,
    level: node.level,
    selectable: node.selectable,
    children: node.children.map(stripMutableFields),
  }
}

export function flattenAccountTree(nodes: AccountTreeNode[]): AccountTreeNode[] {
  return nodes.flatMap((node) => [node, ...flattenAccountTree(node.children)])
}

export function accountMatchesPrefix(accountName: string, prefixes: string[]): boolean {
  return !prefixes.length || prefixes.some((prefix) => accountName === prefix || accountName.startsWith(`${prefix}:`))
}

export function filterAccountNodes(accounts: Account[], prefixes: string[]): AccountTreeNode[] {
  return buildAccountTree(accounts).flatMap((node) => filterNodeByPrefix(node, prefixes))
}

function filterNodeByPrefix(node: AccountTreeNode, prefixes: string[]): AccountTreeNode[] {
  const children = node.children.flatMap((child) => filterNodeByPrefix(child, prefixes))
  if (accountMatchesPrefix(node.name, prefixes)) return [{ ...node, children }]
  return children
}

export function visibleAccountNodes(nodes: AccountTreeNode[], expanded: Set<string>, search = ''): VisibleAccountNode[] {
  const keyword = search.trim().toLowerCase()
  if (keyword) {
    return flattenAccountTree(nodes)
      .filter((node) => accountSearchText(node).includes(keyword))
      .map((node) => ({ ...node, hasChildren: node.children.length > 0 }))
  }
  const result: VisibleAccountNode[] = []
  function walk(items: AccountTreeNode[]) {
    for (const node of items) {
      result.push({ ...node, hasChildren: node.children.length > 0 })
      if (node.children.length && expanded.has(node.name)) walk(node.children)
    }
  }
  walk(nodes)
  return result
}

export function accountSearchText(node: AccountTreeNode): string {
  return `${node.name} ${node.label} ${node.parentPath}`.toLowerCase()
}
