/** Helpers for drawing charts: clean axis ticks and short amounts for axis labels. Values in
 * charts are only used for geometry; every figure the user reads comes from the exact amount. */

const STEPS = [1, 2, 2.5, 5, 10]

/** Round tick values that cover [min, max]: 0 / 500 / 1.000 / 1.500… */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return [0]
  }
  if (min === max) {
    const pad = Math.abs(min) * 0.1 || 1
    min -= pad
    max += pad
  }
  const raw = (max - min) / count
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = (STEPS.find((m) => m * magnitude >= raw) ?? 10) * magnitude
  const first = Math.floor(min / step) * step
  const last = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let value = first; value <= last + step / 2; value += step) {
    ticks.push(Math.round(value * 100) / 100)
  }
  return ticks
}

const COMPACT = new Intl.NumberFormat('es-ES', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

/** "12 mil €", "1,2 M €", "-300 €": for axis ticks, never for the figures themselves. */
export function compactAmount(value: number): string {
  return `${COMPACT.format(value)} €`
}

/** Where a value falls on an axis that goes from `min` (at `bottom`) to `max` (at `top`). */
export function scale(value: number, min: number, max: number, bottom: number, top: number) {
  if (max === min) {
    return (bottom + top) / 2
  }
  return bottom + ((value - min) / (max - min)) * (top - bottom)
}
