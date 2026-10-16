import { describe, expect, it } from 'vitest'

import { amountToInput, parseAmountInput, sumAmounts } from './amount'

describe('parseAmountInput', () => {
  it.each([
    ['12,50', '12.50'],
    ['12,5', '12.50'],
    ['12', '12.00'],
    ['1.234,56', '1234.56'],
    ['1.234', '1234.00'],
    ['12.5', '12.50'],
    ['0,99', '0.99'],
    [' 45,20 € ', '45.20'],
    ['007', '7.00'],
    ['123456789012', '123456789012.00'],
  ])('reads %j as %s', (input, expected) => {
    expect(parseAmountInput(input)).toBe(expected)
  })

  it.each(['', '0', '0,00', 'abc', '12,345', '1,2,3', '-5', '12.345,6.7'])(
    'rejects %j',
    (input) => {
      expect(parseAmountInput(input)).toBeNull()
    },
  )
})

describe('amountToInput', () => {
  it('drops the sign and uses a comma', () => {
    expect(amountToInput('-1234.50')).toBe('1234,50')
  })
})

describe('parseAmountInput options', () => {
  it('accepts zero and negative opening balances when asked', () => {
    expect(parseAmountInput('0', { allowZero: true })).toBe('0.00')
    expect(parseAmountInput('-350,20', { allowNegative: true })).toBe('-350.20')
    expect(parseAmountInput('−350,20', { allowNegative: true })).toBe('-350.20')
    expect(parseAmountInput('-350,20')).toBeNull()
  })
})

describe('sumAmounts', () => {
  it('adds exactly, without floating point', () => {
    expect(sumAmounts(['0.10', '0.20'])).toBe('0.30')
    expect(sumAmounts(['1500.50', '-2000.75'])).toBe('-500.25')
    expect(sumAmounts(['99999999999.99', '0.01'])).toBe('100000000000.00')
    expect(sumAmounts([])).toBe('0.00')
  })
})

describe('amountToInput with sign', () => {
  it('keeps the minus when asked', () => {
    expect(amountToInput('-12.50', true)).toBe('-12,50')
  })
})
