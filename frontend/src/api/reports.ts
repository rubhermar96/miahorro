import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Dashboard = Schemas['DashboardOut']
export type NetWorth = Schemas['NetWorthOut']
export type NetWorthReport = Schemas['NetWorthReport']
export type CashFlowReport = Schemas['CashFlowReport']
export type CashFlowPeriod = Schemas['PeriodOut']
export type SpendingReport = Schemas['SpendingReport']
export type SpendLine = Schemas['SpendLineOut']
export type SpendingBy = SpendingReport['by']
export type Grouping = 'month' | 'year' | 'total'

export const reportKeys = {
  all: ['reports'] as const,
}

type Range = { start?: string; end?: string }

const clean = <T extends Record<string, unknown>>(query: T) =>
  Object.fromEntries(Object.entries(query).filter(([, value]) => value)) as T

export function useDashboard() {
  return useQuery({
    queryKey: [...reportKeys.all, 'dashboard'],
    queryFn: () => unwrap(api.GET('/api/dashboard')),
  })
}

export function useNetWorthReport(range: Range) {
  return useQuery({
    queryKey: [...reportKeys.all, 'net-worth', range],
    queryFn: () => unwrap(api.GET('/api/reports/net-worth', { params: { query: clean(range) } })),
    placeholderData: (previous) => previous,
  })
}

export function useCashFlowReport(range: Range & { group: Grouping }) {
  return useQuery({
    queryKey: [...reportKeys.all, 'cash-flow', range],
    queryFn: () => unwrap(api.GET('/api/reports/cash-flow', { params: { query: clean(range) } })),
    placeholderData: (previous) => previous,
  })
}

export function useSpendingReport(range: Range & { by: SpendingBy }) {
  return useQuery({
    queryKey: [...reportKeys.all, 'spending', range],
    queryFn: () => unwrap(api.GET('/api/reports/spending', { params: { query: clean(range) } })),
    placeholderData: (previous) => previous,
  })
}

/** Where to download everything: same origin, so the session cookie goes along. */
export const EXPORT_JSON = '/api/export.json'
export const EXPORT_ZIP = '/api/export.zip'
