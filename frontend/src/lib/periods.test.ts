import { describe, expect, it } from 'vitest'

import { monthsBetween, periodOf, shiftPeriod, yearRange } from './periods'

describe('financial months', () => {
  it('start on the chosen day', () => {
    expect(periodOf('2026-10-15', 1)).toEqual(['2026-10-01', '2026-10-31'])
    expect(periodOf('2026-10-15', 25)).toEqual(['2026-09-25', '2026-10-24'])
    expect(periodOf('2026-10-25', 25)).toEqual(['2026-10-25', '2026-11-24'])
    expect(periodOf('2026-01-10', 25)).toEqual(['2025-12-25', '2026-01-24'])
  })

  it('move by months', () => {
    expect(shiftPeriod('2026-10-15', -1, 1)).toEqual(['2026-09-01', '2026-09-30'])
    expect(shiftPeriod('2026-01-15', -1, 1)).toEqual(['2025-12-01', '2025-12-31'])
    expect(shiftPeriod('2026-03-10', -1, 25)).toEqual(['2026-01-25', '2026-02-24'])
  })

  it('years and month counts', () => {
    expect(yearRange('2026-10-15')).toEqual(['2026-01-01', '2026-12-31'])
    expect(monthsBetween('2025-11-01', '2026-10-15')).toBe(12)
  })
})
