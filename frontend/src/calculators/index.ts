import { car } from './car'
import { compound } from './compound'
import { home } from './home'
import { mortgage } from './mortgage'
import { personalLoan } from './personalLoan'
import { emergency, savingsGoal } from './saving'
import type { CalculatorDef } from './types'

/** Every calculator, in the order the index shows them. */
export const CALCULATORS: CalculatorDef[] = [
  compound,
  savingsGoal,
  emergency,
  home,
  mortgage,
  car,
  personalLoan,
]

export function calculatorBySlug(slug: string): CalculatorDef | undefined {
  return CALCULATORS.find((calculator) => calculator.slug === slug)
}
