import { formatAmount, formatSignedAmount } from '../lib/format'

/** An amount in Spanish format; with `signed`, income shows "+" and is highlighted. */
export function Money({
  value,
  currency = 'EUR',
  signed = false,
  className = '',
}: {
  value: string
  currency?: string
  signed?: boolean
  className?: string
}) {
  const negative = value.startsWith('-')
  const tone = signed ? (negative ? 'amount--out' : 'amount--in') : ''
  return (
    <span className={['amount', tone, className].filter(Boolean).join(' ')}>
      {signed ? formatSignedAmount(value, currency) : formatAmount(value, currency)}
    </span>
  )
}
