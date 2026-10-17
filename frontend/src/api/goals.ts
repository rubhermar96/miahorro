import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

export type Goal = components['schemas']['GoalOut']
export type GoalInput = components['schemas']['GoalIn']
export type GoalUpdate = components['schemas']['GoalUpdate']
export type Contribution = components['schemas']['ContributionOut']
export type ContributionInput = components['schemas']['ContributionIn']
export type SavingsRate = components['schemas']['SavingsRate']

export const goalKeys = {
  goals: ['goals'] as const,
  savingsRate: ['savings-rate'] as const,
}

export function useGoals() {
  return useQuery({ queryKey: goalKeys.goals, queryFn: () => unwrap(api.GET('/api/goals')) })
}

const goalPath = (id: string) => ({ params: { path: { goal_id: id } } })

export function useGoal(id: string) {
  return useQuery({
    queryKey: [...goalKeys.goals, id],
    enabled: id !== '',
    queryFn: () => unwrap(api.GET('/api/goals/{goal_id}', goalPath(id))),
  })
}

export function useContributions(id: string) {
  return useQuery({
    queryKey: [...goalKeys.goals, id, 'contributions'],
    queryFn: () => unwrap(api.GET('/api/goals/{goal_id}/contributions', goalPath(id))),
  })
}

export function useSavingsRate(months = 6) {
  return useQuery({
    queryKey: [...goalKeys.savingsRate, months],
    queryFn: () => unwrap(api.GET('/api/savings-rate', { params: { query: { months } } })),
  })
}

export const goalsApi = {
  create: (body: GoalInput) => unwrap(api.POST('/api/goals', { body })),
  update: (id: string, body: GoalUpdate) =>
    unwrap(api.PATCH('/api/goals/{goal_id}', { ...goalPath(id), body })),
  remove: (id: string) => unwrap(api.DELETE('/api/goals/{goal_id}', goalPath(id))),
  contribute: (id: string, body: ContributionInput) =>
    unwrap(api.POST('/api/goals/{goal_id}/contributions', { ...goalPath(id), body })),
  removeContribution: (id: string, contributionId: string) =>
    unwrap(
      api.DELETE('/api/goals/{goal_id}/contributions/{contribution_id}', {
        params: { path: { goal_id: id, contribution_id: contributionId } },
      }),
    ),
}
