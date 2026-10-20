import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type CalcContext = Schemas['ContextOut']
export type Reference = Schemas['ReferenceOut']
export type Scenario = Schemas['ScenarioOut']
export type CalcName = Schemas['ScenarioIn']['calculator']

export type CompoundResult = Schemas['CompoundOut']
export type SavingsGoalResult = Schemas['SavingsGoalOut']
export type EmergencyResult = Schemas['EmergencyOut']
export type MortgageResult = Schemas['MortgageOut']
export type MortgageOutcome = Schemas['OutcomeOut']
export type HomeResult = Schemas['HomeOut']
export type CarResult = Schemas['CarOut']
export type CarOutcome = Schemas['CarOutcomeOut']
export type PersonalLoanResult = Schemas['PersonalLoanOut']

/** Request bodies, as the forms build them (validated again by the API). */
export type CalcBody = Record<string, unknown>

export const calcKeys = {
  context: ['calculators', 'context'] as const,
  references: ['calculators', 'references'] as const,
  scenarios: ['scenarios'] as const,
}

/** Run a calculator. Bodies come from the generic form, so they are typed loosely here. */
export function runCalculator(name: CalcName, body: CalcBody): Promise<unknown> {
  // openapi-fetch needs literal paths to type them; the bodies are checked by the API.
  const post = api.POST as unknown as (
    path: string,
    init: { body: CalcBody },
  ) => Promise<{ data?: unknown; error?: unknown; response: Response }>
  return unwrap(post(PATHS[name], { body }))
}

const PATHS: Record<CalcName, string> = {
  compound: '/api/calculators/compound',
  savings_goal: '/api/calculators/savings-goal',
  emergency: '/api/calculators/emergency',
  mortgage: '/api/calculators/mortgage',
  home: '/api/calculators/home',
  car: '/api/calculators/car',
  personal_loan: '/api/calculators/personal-loan',
}

export function useCalcContext() {
  return useQuery({
    queryKey: calcKeys.context,
    queryFn: () => unwrap(api.GET('/api/calculators/context')),
  })
}

export function useReferences() {
  return useQuery({
    queryKey: calcKeys.references,
    queryFn: () => unwrap(api.GET('/api/calculators/references')),
  })
}

export function useScenarios(calculator: CalcName) {
  return useQuery({
    queryKey: [...calcKeys.scenarios, calculator],
    queryFn: () => unwrap(api.GET('/api/scenarios', { params: { query: { calculator } } })),
  })
}

const scenarioPath = (id: string) => ({ params: { path: { scenario_id: id } } })

export const scenariosApi = {
  create: (calculator: CalcName, name: string, inputs: CalcBody) =>
    unwrap(api.POST('/api/scenarios', { body: { calculator, name, inputs } })),
  update: (id: string, body: { name?: string; inputs?: CalcBody }) =>
    unwrap(api.PATCH('/api/scenarios/{scenario_id}', { ...scenarioPath(id), body })),
  remove: (id: string) => unwrap(api.DELETE('/api/scenarios/{scenario_id}', scenarioPath(id))),
}
