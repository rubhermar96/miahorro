import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type Loan = components['schemas']['LoanOut']
export type LoanInput = components['schemas']['LoanFields']
export type LoanUpdate = components['schemas']['LoanUpdate']
export type Installment = components['schemas']['InstallmentOut']
export type Simulation = components['schemas']['SimulationOut']
export type SimulationInput = components['schemas']['SimulationIn']
export type LoanPrepayment = components['schemas']['PrepaymentOut']
export type ReferenceRate = components['schemas']['ReferenceRateOut']
export type LoanKind = LoanInput['kind']

export const LOAN_KINDS: NonNullable<LoanKind>[] = [
  'mortgage',
  'personal',
  'car',
  'consumer',
  'credit_line',
  'p2p_owe',
  'p2p_lent',
]

export const loanKeys = {
  loans: ['loans'] as const,
  rates: ['reference-rates'] as const,
}

const loanPath = (id: string) => ({ params: { path: { loan_id: id } } })

export function useLoans() {
  return useQuery({ queryKey: loanKeys.loans, queryFn: () => unwrap(api.GET('/api/loans')) })
}

export function useLoan(id: string) {
  return useQuery({
    queryKey: [...loanKeys.loans, id],
    enabled: id !== '',
    queryFn: () => unwrap(api.GET('/api/loans/{loan_id}', loanPath(id))),
  })
}

export function useSchedule(id: string) {
  return useQuery({
    queryKey: [...loanKeys.loans, id, 'schedule'],
    queryFn: () => unwrap(api.GET('/api/loans/{loan_id}/schedule', loanPath(id))),
  })
}

export function usePrepayments(id: string) {
  return useQuery({
    queryKey: [...loanKeys.loans, id, 'prepayments'],
    queryFn: () => unwrap(api.GET('/api/loans/{loan_id}/prepayments', loanPath(id))),
  })
}

export function useReferenceRates() {
  return useQuery({
    queryKey: loanKeys.rates,
    queryFn: () => unwrap(api.GET('/api/reference-rates')),
  })
}

export const loansApi = {
  create: (body: LoanInput) => unwrap(api.POST('/api/loans', { body })),
  update: (id: string, body: LoanUpdate) =>
    unwrap(api.PATCH('/api/loans/{loan_id}', { ...loanPath(id), body })),
  remove: (id: string) => unwrap(api.DELETE('/api/loans/{loan_id}', loanPath(id))),
  simulate: (id: string, body: SimulationInput) =>
    unwrap(api.POST('/api/loans/{loan_id}/simulate', { ...loanPath(id), body })),
  addPrepayment: (id: string, body: SimulationInput) =>
    unwrap(api.POST('/api/loans/{loan_id}/prepayments', { ...loanPath(id), body })),
  removePrepayment: (id: string, prepaymentId: string) =>
    unwrap(
      api.DELETE('/api/loans/{loan_id}/prepayments/{prepayment_id}', {
        params: { path: { loan_id: id, prepayment_id: prepaymentId } },
      }),
    ),
  setRate: (month: string, value: string) =>
    unwrap(api.PUT('/api/reference-rates', { body: { index: 'euribor_12m', month, value } })),
  removeRate: (id: string) =>
    unwrap(api.DELETE('/api/reference-rates/{rate_id}', { params: { path: { rate_id: id } } })),
}
