/**
 * Spanish formatting for amounts and dates.
 *
 * Amounts arrive from the API as decimal strings ("1234.56") and are formatted with integer
 * arithmetic only, never through floating point (RNF-04). Rounding to the cent is half-up,
 * away from zero, matching the backend policy.
 */

const AMOUNT_PATTERN = /^(-)?(\d+)(?:\.(\d+))?$/
const NBSP = ' '

const CURRENCY_SYMBOLS: Record<string, string> = { EUR: '€' }

/** Format a decimal string as "1.234,56 €". Throws if the value is not a plain decimal. */
export function formatAmount(value: string, currency = 'EUR'): string {
  const match = AMOUNT_PATTERN.exec(value)
  if (!match) {
    throw new Error(`Not a decimal amount: ${JSON.stringify(value)}`)
  }
  const [, sign, integerDigits = '0', fractionDigits = ''] = match

  // Truncate to thousandths, then round half-up to cents. The third decimal alone decides
  // whether the amount reaches half a cent, so later digits can be dropped safely.
  const thousandths = BigInt(integerDigits + fractionDigits.padEnd(3, '0').slice(0, 3))
  const cents = (thousandths + 5n) / 10n

  const isNegative = sign === '-' && cents !== 0n
  const units = (cents / 100n).toString()
  const centsPart = (cents % 100n).toString().padStart(2, '0')
  const grouped = units.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency

  return `${isNegative ? '-' : ''}${grouped},${centsPart}${NBSP}${symbol}`
}

const DATE_FORMAT = new Intl.DateTimeFormat('es-ES', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** Format an ISO date ("2026-10-14") as "14 oct 2026", without timezone shifts. */
export function formatDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  if (!match) {
    throw new Error(`Not an ISO date: ${JSON.stringify(isoDate)}`)
  }
  const [, year, month, day] = match.map(Number)
  return DATE_FORMAT.format(new Date(year!, month! - 1, day))
}
