import type { TFunction } from 'i18next'

import type { Goal } from '../api/goals'
import { formatAmount, formatMonthYear } from './format'

/** The status line, in words: "on track", "behind", "no date"… */
export function goalStatusText(goal: Goal, t: TFunction): string {
  const when = goal.estimated_date ? formatMonthYear(goal.estimated_date) : null
  switch (goal.status) {
    case 'achieved':
      return t('goals.status.achieved')
    case 'on_track':
      return t('goals.status.onTrack', { date: when })
    case 'behind':
      return t('goals.status.behind', {
        amount: formatAmount(goal.required_monthly ?? '0'),
        pace: formatAmount(goal.pace ?? '0'),
      })
    case 'starting':
      return t('goals.status.starting', { amount: formatAmount(goal.required_monthly ?? '0') })
    default:
      return when ? t('goals.status.noDateWithPace', { date: when }) : t('goals.status.noDate')
  }
}
