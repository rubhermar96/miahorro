import type { TFunction } from 'i18next'
import type { ComponentType } from 'react'

import type { CalcContext, CalcName } from '../api/calculators'
import type { Body, FormValues, SectionSpec } from '../lib/calcForm'

/** One figure of a result, for the side-by-side comparison of scenarios. */
export type Metric = { label: string; value: string }

export type ResultProps<R> = { result: R; values: FormValues; context?: CalcContext }

export type ExtraProps = {
  context: CalcContext
  values: FormValues
  onChange: (values: FormValues) => void
}

export type CalculatorDef<R = unknown> = {
  name: CalcName
  /** URL segment, in Spanish */
  slug: string
  icon: string
  group: 'saving' | 'buying'
  sections: SectionSpec[]
  /** Starting values, with the user's own figures when there are any. */
  defaults: (context: CalcContext | undefined) => FormValues
  /** Adjust the body built from the form (and undo it to reopen a saved scenario). */
  finalize?: (body: Body) => Body
  restore?: (body: Body) => Body
  Result: ComponentType<ResultProps<R>>
  metrics: (result: R, t: TFunction) => Metric[]
  /** Helpers above the form, such as picking essential categories. */
  Extra?: ComponentType<ExtraProps>
}

/** Keep each definition's own result type while listing them together. */
export function define<R>(def: CalculatorDef<R>): CalculatorDef {
  return def as unknown as CalculatorDef
}

/** A positive figure from the context as typed text ("1234,5"), or '' if there is none. */
export function contextAmount(value: string | undefined): string {
  if (!value || value.startsWith('-') || value === '0.00') {
    return ''
  }
  return value.replace(/\.00$/, '').replace('.', ',')
}
