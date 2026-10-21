import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Investment = Schemas['InvestmentOut']
export type InvestmentDetail = Schemas['InvestmentDetail']
export type InvestmentInput = Schemas['InvestmentFields']
export type InvestmentUpdate = Schemas['InvestmentUpdate']
export type InvestmentKind = NonNullable<InvestmentInput['kind']>
export type Operation = Schemas['OperationOut']
export type OperationInput = Schemas['OperationIn']
export type OperationKind = Operation['kind']
export type InvestmentPrice = Schemas['PriceOut']
export type Portfolio = Schemas['PortfolioOut']
export type TaxReport = Schemas['TaxReportOut']

export const INVESTMENT_KINDS: InvestmentKind[] = ['fund', 'etf', 'stock', 'pension_plan']
export const OPERATION_KINDS: OperationKind[] = [
  'buy',
  'sell',
  'dividend',
  'fee',
  'split',
  'transfer',
]

export const investmentKeys = {
  all: ['investments'] as const,
  portfolio: ['investments', 'portfolio'] as const,
}

const path = (id: string) => ({ params: { path: { investment_id: id } } })

export function useInvestments(includeArchived = false) {
  return useQuery({
    queryKey: [...investmentKeys.all, 'list', includeArchived],
    queryFn: () =>
      unwrap(
        api.GET('/api/investments', { params: { query: { include_archived: includeArchived } } }),
      ),
  })
}

export function useInvestment(id: string) {
  return useQuery({
    queryKey: [...investmentKeys.all, id],
    enabled: id !== '',
    queryFn: () => unwrap(api.GET('/api/investments/{investment_id}', path(id))),
  })
}

export function useOperations(id: string) {
  return useQuery({
    queryKey: [...investmentKeys.all, id, 'operations'],
    enabled: id !== '',
    queryFn: () => unwrap(api.GET('/api/investments/{investment_id}/operations', path(id))),
  })
}

export function usePrices(id: string) {
  return useQuery({
    queryKey: [...investmentKeys.all, id, 'prices'],
    queryFn: () => unwrap(api.GET('/api/investments/{investment_id}/prices', path(id))),
  })
}

export function usePortfolio() {
  return useQuery({
    queryKey: investmentKeys.portfolio,
    queryFn: () => unwrap(api.GET('/api/portfolio')),
  })
}

export function useTaxReport(year: number) {
  return useQuery({
    queryKey: [...investmentKeys.all, 'tax-report', year],
    queryFn: () => unwrap(api.GET('/api/portfolio/tax-report', { params: { query: { year } } })),
  })
}

const opPath = (id: string, operationId: string) => ({
  params: { path: { investment_id: id, operation_id: operationId } },
})

export const investmentsApi = {
  create: (body: InvestmentInput) => unwrap(api.POST('/api/investments', { body })),
  update: (id: string, body: InvestmentUpdate) =>
    unwrap(api.PATCH('/api/investments/{investment_id}', { ...path(id), body })),
  remove: (id: string) => unwrap(api.DELETE('/api/investments/{investment_id}', path(id))),
  addOperation: (id: string, body: OperationInput) =>
    unwrap(api.POST('/api/investments/{investment_id}/operations', { ...path(id), body })),
  replaceOperation: (id: string, operationId: string, body: OperationInput) =>
    unwrap(
      api.PUT('/api/investments/{investment_id}/operations/{operation_id}', {
        ...opPath(id, operationId),
        body,
      }),
    ),
  removeOperation: (id: string, operationId: string) =>
    unwrap(
      api.DELETE(
        '/api/investments/{investment_id}/operations/{operation_id}',
        opPath(id, operationId),
      ),
    ),
  setPrice: (id: string, date: string, price: string) =>
    unwrap(
      api.PUT('/api/investments/{investment_id}/prices', { ...path(id), body: { date, price } }),
    ),
  removePrice: (id: string, priceId: string) =>
    unwrap(
      api.DELETE('/api/investments/{investment_id}/prices/{price_id}', {
        params: { path: { investment_id: id, price_id: priceId } },
      }),
    ),
}
