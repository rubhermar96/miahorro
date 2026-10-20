/** A typed percentage ("2,15", "-0,3") as the API expects it ("2.15"); null if invalid. */
export function parseRateInput(text: string, { allowNegative = false } = {}): string | null {
  const value = text.trim().replace(',', '.').replace('%', '').trim()
  const pattern = allowNegative ? /^-?\d{1,3}(\.\d{1,4})?$/ : /^\d{1,3}(\.\d{1,4})?$/
  return pattern.test(value) ? value : null
}

/** An API rate ("2.1500") for an input field ("2,15"). */
export function rateToInput(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  return value.includes('.') ? value.replace(/\.?0+$/, '').replace('.', ',') : value
}
