import { describe, expect, it } from 'vitest'

import { formatPrice, formatUnits, parseUnitsInput, unitsToInput } from './units'

describe('units', () => {
  it('reads quantities the Spanish way, up to six decimals', () => {
    expect(parseUnitsInput('12,5')).toBe('12.5')
    expect(parseUnitsInput('1.234,567891')).toBe('1234.567891')
    expect(parseUnitsInput('12.345678')).toBe('12.345678')
    expect(parseUnitsInput('1.234')).toBe('1234')
    expect(parseUnitsInput('10,500000')).toBe('10.5')
    expect(parseUnitsInput(' 3 ')).toBe('3')
  })

  it('refuses what is not a positive quantity', () => {
    expect(parseUnitsInput('')).toBeNull()
    expect(parseUnitsInput('0')).toBeNull()
    expect(parseUnitsInput('0', { allowZero: true })).toBe('0')
    expect(parseUnitsInput('1,1234567')).toBeNull()
    expect(parseUnitsInput('-3')).toBeNull()
    expect(parseUnitsInput('doce')).toBeNull()
  })

  it('shows quantities and prices', () => {
    expect(formatUnits('1234.5')).toBe('1.234,5')
    expect(formatUnits('10')).toBe('10')
    expect(formatPrice('112.345600')).toBe('112,3456 €')
    expect(unitsToInput('12.5')).toBe('12,5')
  })
})
