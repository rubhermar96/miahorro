import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type CaptureToken = components['schemas']['TokenOut']
export type NewCaptureToken = components['schemas']['NewToken']
export type CaptureCard = components['schemas']['CardOut']
export type RecurringItem = components['schemas']['RecurringOut']
export type RecurringInput = components['schemas']['RecurringIn']
export type Upcoming = components['schemas']['Upcoming']
export type Inbox = components['schemas']['Inbox']

export const captureKeys = {
  tokens: ['capture', 'tokens'] as const,
  cards: ['capture', 'cards'] as const,
  recurring: ['recurring'] as const,
  inbox: ['inbox'] as const,
}

export function useCaptureTokens() {
  return useQuery({
    queryKey: captureKeys.tokens,
    queryFn: () => unwrap(api.GET('/api/capture/tokens')),
  })
}

export function useCaptureCards() {
  return useQuery({
    queryKey: captureKeys.cards,
    queryFn: () => unwrap(api.GET('/api/capture/cards')),
  })
}

export function useRecurring() {
  return useQuery({
    queryKey: captureKeys.recurring,
    queryFn: () => unwrap(api.GET('/api/recurring')),
  })
}

export function useUpcoming(days = 30) {
  return useQuery({
    queryKey: [...captureKeys.recurring, 'upcoming', days],
    queryFn: () => unwrap(api.GET('/api/recurring/upcoming', { params: { query: { days } } })),
  })
}

export function useInbox() {
  return useQuery({ queryKey: captureKeys.inbox, queryFn: () => unwrap(api.GET('/api/inbox')) })
}

const recurringPath = (id: string) => ({ params: { path: { item_id: id } } })

export const captureApi = {
  createToken: (name: string, accountId: string) =>
    unwrap(api.POST('/api/capture/tokens', { body: { name, default_account_id: accountId } })),
  revokeToken: (id: string) =>
    unwrap(api.DELETE('/api/capture/tokens/{token_id}', { params: { path: { token_id: id } } })),
  mapCard: (id: string, accountId: string) =>
    unwrap(
      api.PATCH('/api/capture/cards/{card_id}', {
        params: { path: { card_id: id } },
        body: { account_id: accountId },
      }),
    ),

  createRecurring: (body: RecurringInput) => unwrap(api.POST('/api/recurring', { body })),
  updateRecurring: (id: string, body: RecurringInput) =>
    unwrap(api.PUT('/api/recurring/{item_id}', { ...recurringPath(id), body })),
  deleteRecurring: (id: string) =>
    unwrap(api.DELETE('/api/recurring/{item_id}', recurringPath(id))),

  confirm: (transactionId: string) =>
    unwrap(
      api.POST('/api/transactions/{transaction_id}/confirm', {
        params: { path: { transaction_id: transactionId } },
      }),
    ),
}
