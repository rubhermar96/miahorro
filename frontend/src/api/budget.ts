import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type Budget = components['schemas']['BudgetOut']
export type BudgetLine = components['schemas']['LineOut']
export type BudgetMode = NonNullable<Budget['mode']>

export const budgetKeys = { budget: ['budget'] as const }

/** The financial month that contains `date` (today if empty). */
export function useBudget(date: string) {
  return useQuery({
    queryKey: [...budgetKeys.budget, date],
    queryFn: () => unwrap(api.GET('/api/budget', { params: { query: date ? { date } : {} } })),
  })
}

const linePath = (categoryId: string) => ({ params: { path: { category_id: categoryId } } })

export const budgetApi = {
  setLine: (categoryId: string, amount: string, date: string | null) =>
    unwrap(
      api.PUT('/api/budget/lines/{category_id}', {
        ...linePath(categoryId),
        body: { amount, date },
      }),
    ),
  removeLine: (categoryId: string, date: string) =>
    unwrap(
      api.DELETE('/api/budget/lines/{category_id}', {
        params: { path: { category_id: categoryId }, query: { date } },
      }),
    ),
  move: (from: string, to: string, amount: string, date: string) =>
    unwrap(
      api.POST('/api/budget/move', {
        body: { from_category_id: from, to_category_id: to, amount, date },
      }),
    ),
  copyPrevious: (date: string) => unwrap(api.POST('/api/budget/copy-previous', { body: { date } })),
}
