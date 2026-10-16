import { type QueryClient, useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type Account = components['schemas']['AccountOut']
export type AccountInput = components['schemas']['AccountIn']
export type AccountUpdate = components['schemas']['AccountUpdate']
export type AccountKind = Account['kind']
export type AccountRate = components['schemas']['AccountRateOut']
export type AccountRateInput = components['schemas']['AccountRateIn']
export type Category = components['schemas']['CategoryOut']
export type CategoryInput = components['schemas']['CategoryIn']
export type CategoryUpdate = components['schemas']['CategoryUpdate']
export type Transaction = components['schemas']['TransactionOut']
export type TransactionInput = components['schemas']['TransactionIn']
export type TransactionUpdate = components['schemas']['TransactionUpdate']
export type TransferInput = components['schemas']['TransferIn']
export type TransactionPage = components['schemas']['TransactionPage']

export type TransactionFilters = {
  account_id?: string
  category_id?: string
  kind?: Transaction['kind']
  tag?: string
  q?: string
  date_from?: string
  date_to?: string
}

export const ACCOUNT_KINDS: AccountKind[] = [
  'checking',
  'savings',
  'deposit',
  'credit_card',
  'cash',
  'wallet',
  'brokerage',
  'crypto',
]

const PAGE_SIZE = 50

export const financeKeys = {
  accounts: ['accounts'] as const,
  categories: ['categories'] as const,
  transactions: ['transactions'] as const,
  tags: ['tags'] as const,
}

/** After any change to money, every derived view (balances, lists, usage) is refreshed. */
export function refreshFinance(queryClient: QueryClient) {
  return Promise.all(
    Object.values(financeKeys).map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  )
}

export function useAccounts(includeArchived = false) {
  return useQuery({
    queryKey: [...financeKeys.accounts, { includeArchived }],
    queryFn: () =>
      unwrap(
        api.GET('/api/accounts', { params: { query: { include_archived: includeArchived } } }),
      ),
  })
}

export function useAccount(id: string) {
  return useQuery({
    queryKey: [...financeKeys.accounts, id],
    queryFn: () =>
      unwrap(api.GET('/api/accounts/{account_id}', { params: { path: { account_id: id } } })),
  })
}

export function useAccountRates(id: string) {
  return useQuery({
    queryKey: [...financeKeys.accounts, id, 'rates'],
    queryFn: () =>
      unwrap(api.GET('/api/accounts/{account_id}/rates', { params: { path: { account_id: id } } })),
  })
}

export function useCategories(includeArchived = false) {
  return useQuery({
    queryKey: [...financeKeys.categories, { includeArchived }],
    queryFn: () =>
      unwrap(
        api.GET('/api/categories', { params: { query: { include_archived: includeArchived } } }),
      ),
  })
}

export function useTags() {
  return useQuery({
    queryKey: financeKeys.tags,
    queryFn: () => unwrap(api.GET('/api/tags')),
  })
}

export function useTransactions(filters: TransactionFilters) {
  return useInfiniteQuery({
    queryKey: [...financeKeys.transactions, filters],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/transactions', {
          params: { query: { ...filters, limit: PAGE_SIZE, offset: pageParam } },
        }),
      ),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((count, page) => count + page.items.length, 0)
      return loaded < last.total ? loaded : undefined
    },
  })
}

export function useTransaction(id: string) {
  return useQuery({
    queryKey: [...financeKeys.transactions, 'one', id],
    queryFn: () =>
      unwrap(
        api.GET('/api/transactions/{transaction_id}', {
          params: { path: { transaction_id: id } },
        }),
      ),
  })
}

const accountPath = (id: string) => ({ params: { path: { account_id: id } } })
const transactionPath = (id: string) => ({ params: { path: { transaction_id: id } } })
const categoryPath = (id: string) => ({ params: { path: { category_id: id } } })

export const financeApi = {
  createAccount: (body: AccountInput) => unwrap(api.POST('/api/accounts', { body })),
  updateAccount: (id: string, body: AccountUpdate) =>
    unwrap(api.PATCH('/api/accounts/{account_id}', { ...accountPath(id), body })),
  deleteAccount: (id: string) => unwrap(api.DELETE('/api/accounts/{account_id}', accountPath(id))),
  addRate: (id: string, body: AccountRateInput) =>
    unwrap(api.POST('/api/accounts/{account_id}/rates', { ...accountPath(id), body })),
  deleteRate: (id: string, rateId: string) =>
    unwrap(
      api.DELETE('/api/accounts/{account_id}/rates/{rate_id}', {
        params: { path: { account_id: id, rate_id: rateId } },
      }),
    ),
  reconcile: (id: string, balance: string) =>
    unwrap(
      api.POST('/api/accounts/{account_id}/reconcile', { ...accountPath(id), body: { balance } }),
    ),

  createTransaction: (body: TransactionInput) => unwrap(api.POST('/api/transactions', { body })),
  updateTransaction: (id: string, body: TransactionUpdate) =>
    unwrap(api.PATCH('/api/transactions/{transaction_id}', { ...transactionPath(id), body })),
  deleteTransaction: (id: string) =>
    unwrap(api.DELETE('/api/transactions/{transaction_id}', transactionPath(id))),
  createTransfer: (body: TransferInput) => unwrap(api.POST('/api/transfers', { body })),

  createCategory: (body: CategoryInput) => unwrap(api.POST('/api/categories', { body })),
  updateCategory: (id: string, body: CategoryUpdate) =>
    unwrap(api.PATCH('/api/categories/{category_id}', { ...categoryPath(id), body })),
  deleteCategory: (id: string) =>
    unwrap(api.DELETE('/api/categories/{category_id}', categoryPath(id))),
}

export type CategoryNode = Category & { children: Category[] }

/** Main categories with their subcategories, for one kind (expense or income). */
export function categoryTree(categories: Category[], kind: Category['kind']): CategoryNode[] {
  const mains = categories.filter((c) => c.kind === kind && c.parent_id === null)
  return mains.map((main) => ({
    ...main,
    children: categories.filter((c) => c.parent_id === main.id),
  }))
}

/** "Alimentación › Supermercado", or just the name of a main category. */
export function categoryLabel(
  categories: Category[],
  id: string | null | undefined,
): string | null {
  const category = categories.find((c) => c.id === id)
  if (!category) {
    return null
  }
  const parent = categories.find((c) => c.id === category.parent_id)
  return parent ? `${parent.name} › ${category.name}` : category.name
}

/** The icon of a category, or of its main category. */
export function categoryIcon(categories: Category[], id: string | null | undefined): string {
  const category = categories.find((c) => c.id === id)
  if (!category) {
    return '·'
  }
  const parent = categories.find((c) => c.id === category.parent_id)
  return category.icon ?? parent?.icon ?? '·'
}
