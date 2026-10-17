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

/** Like formatAmount, with an explicit "+" for money coming in ("+2.000,00 €"). */
export function formatSignedAmount(value: string, currency = 'EUR'): string {
  const formatted = formatAmount(value, currency)
  return value.startsWith('-') || /^0*(\.0*)?$/.test(value) ? formatted : `+${formatted}`
}

/** Today's date in Spain as "2026-10-16", for date inputs. */
export function todayIso(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Madrid',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
  return parts // en-CA formats as YYYY-MM-DD
}

const DAY_FORMAT = new Intl.DateTimeFormat('es-ES', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
})

/** "jueves, 16 de octubre" for list headers. */
export function formatDay(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return DAY_FORMAT.format(new Date(year!, month! - 1, day))
}

/** An API rate ("2.1500") the Spanish way, without trailing zeros ("2,15"). */
export function formatRate(value: string): string {
  return value.includes('.') ? value.replace(/\.?0+$/, '').replace('.', ',') : value
}

function isoParts(isoDate: string): [number, number, number] {
  const [year, month, day] = isoDate.split('-').map(Number)
  return [year!, month!, day!]
}

const MONTH_YEAR_FORMAT = new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' })

/** "marzo de 2028", for forecasts where the day does not matter. */
export function formatMonthYear(isoDate: string): string {
  const [year, month, day] = isoParts(isoDate)
  return MONTH_YEAR_FORMAT.format(new Date(year, month - 1, day))
}

const SHORT_DATE_FORMAT = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' })

/** "25 sep", for compact lists of recent periods. */
export function formatShortDate(isoDate: string): string {
  const [year, month, day] = isoParts(isoDate)
  return SHORT_DATE_FORMAT.format(new Date(year, month - 1, day))
}
