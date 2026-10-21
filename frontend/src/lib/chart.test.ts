import { describe, expect, it } from 'vitest'

import { compactAmount, niceTicks, scale } from './chart'

describe('chart helpers', () => {
  it('picks round ticks that cover the values', () => {
    expect(niceTicks(0, 1800)).toEqual([0, 500, 1000, 1500, 2000])
    expect(niceTicks(-1200, 3100)).toEqual([-2000, 0, 2000, 4000])
    expect(niceTicks(12_340, 12_990)).toEqual([12_200, 12_400, 12_600, 12_800, 13_000])
    expect(niceTicks(100, 100)).toEqual([90, 95, 100, 105, 110])
  })

  it('writes short amounts for axes', () => {
    expect(compactAmount(12_000)).toBe('12 mil €')
    expect(compactAmount(1_250_000)).toBe('1,3 M €')
    expect(compactAmount(-300)).toBe('-300 €')
  })

  it('scales values to pixels', () => {
    expect(scale(50, 0, 100, 200, 0)).toBe(100)
    expect(scale(5, 5, 5, 200, 0)).toBe(100)
  })
})
