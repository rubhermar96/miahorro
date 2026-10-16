/**
 * Amounts the way Spanish users type them, converted to and from the API format ("1234.56").
 * Everything works on strings and BigInt cents: no floating point is involved (RNF-04).
 */

type ParseOptions = { allowZero?: boolean; allowNegative?: boolean }

/**
 * Read an amount typed by the user ("12,50", "1.234,5", "12.5") as an API amount ("12.50").
 * Returns null when it is not valid. By default the amount must be positive; opening balances
 * may also be zero or negative (a credit card that owes money).
 */
export function parseAmountInput(input: string, options: ParseOptions = {}): string | null {
  let text = input.replace(/[\s€]/g, '')
  let sign = ''
  if (options.allowNegative && /^[-−]/.test(text)) {
    sign = '-'
    text = text.slice(1)
  }
  if (!text) {
    return null
  }
  let normalised: string
  if (text.includes(',')) {
    // Comma is the decimal separator; dots may only group thousands before it.
    if (!/^(\d+|\d{1,3}(\.\d{3})+),\d{1,2}$/.test(text)) {
      return null
    }
    normalised = text.replace(/\./g, '').replace(',', '.')
  } else if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
    normalised = text.replace(/\./g, '') // "1.234" is one thousand two hundred and thirty-four
  } else {
    normalised = text // "12.5" typed with a dot still means twelve and a half
  }
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalised)
  if (!match) {
    return null
  }
  const [, units = '0', cents = ''] = match
  const value = `${BigInt(units).toString()}.${cents.padEnd(2, '0')}`
  if (value === '0.00') {
    return options.allowZero ? value : null
  }
  return sign + value
}

/** "-12.50" -> "12,50" for editing an existing amount (keepSign keeps the minus). */
export function amountToInput(value: string, keepSign = false): string {
  const text = keepSign ? value : value.replace('-', '')
  return text.replace('.', ',')
}

function toCents(value: string): bigint {
  const negative = value.startsWith('-')
  const [units = '0', decimals = ''] = value.replace('-', '').split('.')
  const cents = BigInt(units) * 100n + BigInt(decimals.padEnd(2, '0').slice(0, 2))
  return negative ? -cents : cents
}

/** Exact sum of API amounts: ["0.10", "0.20"] -> "0.30". */
export function sumAmounts(values: string[]): string {
  const total = values.reduce((sum, value) => sum + toCents(value), 0n)
  const negative = total < 0n
  const absolute = negative ? -total : total
  const units = absolute / 100n
  const cents = (absolute % 100n).toString().padStart(2, '0')
  return `${negative ? '-' : ''}${units}.${cents}`
}
