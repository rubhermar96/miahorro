/**
 * Participaciones, shares and prices per unit: up to six decimals, typed the Spanish way
 * ("1.234,567891") and sent as the API expects them ("1234.567891"). Strings throughout.
 */

const MAX_DECIMALS = 6

/** "12,5" → "12.5"; "1.234,5" → "1234.5"; null if it is not a positive quantity. */
export function parseUnitsInput(input: string, { allowZero = false } = {}): string | null {
  const text = input.replace(/\s/g, '').replace(/€$/, '')
  if (!text) {
    return null
  }
  let normalised: string
  if (text.includes(',')) {
    if (!/^(\d+|\d{1,3}(\.\d{3})+),\d+$/.test(text)) {
      return null
    }
    normalised = text.replace(/\./g, '').replace(',', '.')
  } else if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
    normalised = text.replace(/\./g, '') // "1.234" groups thousands, as with amounts
  } else {
    normalised = text
  }
  const match = /^(\d+)(?:\.(\d+))?$/.exec(normalised)
  if (!match) {
    return null
  }
  const [, units = '0', decimals = ''] = match
  if (decimals.length > MAX_DECIMALS) {
    return null
  }
  const trimmed = decimals.replace(/0+$/, '')
  const value = `${BigInt(units).toString()}${trimmed ? `.${trimmed}` : ''}`
  if (value === '0' && !allowZero) {
    return null
  }
  return value
}

/** "1234.5" → "1.234,5", as a number of units. */
export function formatUnits(value: string): string {
  const [units = '0', decimals = ''] = value.split('.')
  const grouped = units.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  const rest = decimals.replace(/0+$/, '')
  return rest ? `${grouped},${rest}` : grouped
}

/** A price per unit: "112.345600" → "112,3456 €". */
export function formatPrice(value: string): string {
  return `${formatUnits(value)} €`
}

/** An API quantity for an input field: "12.5" → "12,5". */
export function unitsToInput(value: string | null | undefined): string {
  return value ? value.replace('.', ',') : ''
}
