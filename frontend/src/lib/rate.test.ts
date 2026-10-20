import { describe, expect, it } from 'vitest'

import { parseRateInput, rateToInput } from './rate'

describe('rates', () => {
  it('reads Spanish percentages', () => {
    expect(parseRateInput('2,15')).toBe('2.15')
    expect(parseRateInput(' 3 % ')).toBe('3')
    expect(parseRateInput('0,0725')).toBe('0.0725')
    expect(parseRateInput('-0,3')).toBeNull()
    expect(parseRateInput('-0,3', { allowNegative: true })).toBe('-0.3')
    expect(parseRateInput('dos')).toBeNull()
    expect(parseRateInput('1,23456')).toBeNull()
  })

  it('writes rates back for editing', () => {
    expect(rateToInput('2.1500')).toBe('2,15')
    expect(rateToInput('5.0000')).toBe('5')
    expect(rateToInput(null)).toBe('')
  })
})
