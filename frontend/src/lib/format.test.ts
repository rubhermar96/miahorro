import { describe, expect, it } from 'vitest'

import {
  formatAmount,
  formatDate,
  formatDay,
  formatMonthYear,
  formatShortDate,
  formatSignedAmount,
  todayIso,
} from './format'

const NBSP = ' '

describe('formatAmount', () => {
  it.each([
    ['1234.56', '1.234,56'],
    ['1000', '1.000,00'],
    ['999.9', '999,90'],
    ['0', '0,00'],
    ['12', '12,00'],
    ['-0.5', '-0,50'],
    ['-1234567.8', '-1.234.567,80'],
    ['123456789012345678.99', '123.456.789.012.345.678,99'],
  ])('formats %s as %s €', (value, expected) => {
    expect(formatAmount(value)).toBe(`${expected}${NBSP}€`)
  })

  it.each([
    ['0.005', '0,01'],
    ['-0.005', '-0,01'],
    ['2.675', '2,68'],
    ['1.0049999', '1,00'],
    ['1.0051', '1,01'],
    ['999.995', '1.000,00'],
  ])('rounds %s half-up to %s €', (value, expected) => {
    expect(formatAmount(value)).toBe(`${expected}${NBSP}€`)
  })

  it('does not show a sign for amounts that round to zero', () => {
    expect(formatAmount('-0.004')).toBe(`0,00${NBSP}€`)
  })

  it('uses the currency code when there is no known symbol', () => {
    expect(formatAmount('10', 'USD')).toBe(`10,00${NBSP}USD`)
  })

  it.each(['1,5', '1.234,56', 'abc', '', '1e3', ' 1'])('rejects %j', (value) => {
    expect(() => formatAmount(value)).toThrow('Not a decimal amount')
  })
})

describe('formatDate', () => {
  it('formats ISO dates in Spanish without shifting the day', () => {
    expect(formatDate('2026-10-14')).toMatch(/^14 oct\.? 2026$/)
    expect(formatDate('2026-01-01')).toMatch(/^1 ene\.? 2026$/)
  })

  it('rejects values that are not ISO dates', () => {
    expect(() => formatDate('14/10/2026')).toThrow('Not an ISO date')
  })
})

describe('formatSignedAmount', () => {
  it('marks income with a plus sign', () => {
    expect(formatSignedAmount('2000')).toBe(`+2.000,00${NBSP}€`)
    expect(formatSignedAmount('-12.5')).toBe(`-12,50${NBSP}€`)
    expect(formatSignedAmount('0.00')).toBe(`0,00${NBSP}€`)
  })
})

describe('todayIso', () => {
  it('uses the Spanish date, not UTC', () => {
    // 23:30 UTC on 15 October is already 16 October in Madrid (summer time).
    expect(todayIso(new Date('2026-10-15T23:30:00Z'))).toBe('2026-10-16')
  })
})

describe('formatDay', () => {
  it('formats a list header', () => {
    expect(formatDay('2026-10-16')).toBe('viernes, 16 de octubre')
  })
})

describe('month and short dates', () => {
  it('formats forecasts and periods', () => {
    expect(formatMonthYear('2028-03-16')).toBe('marzo de 2028')
    expect(formatShortDate('2026-09-25')).toBe('25 sept')
  })
})
