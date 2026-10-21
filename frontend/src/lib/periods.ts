/** Financial months (RF-USR-04), like the backend's finance/periods.py: each starts on the
 * user's chosen day, from 1 to 28. Dates are ISO strings; no time zones involved. */

function iso(year: number, month: number, day: number): string {
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.toISOString().slice(0, 10)
}

function parts(date: string): [number, number, number] {
  const [year, month, day] = date.split('-').map(Number)
  return [year!, month!, day!]
}

/** First and last day of the financial month that contains `date`. */
export function periodOf(date: string, startDay: number): [string, string] {
  const [year, month, day] = parts(date)
  const startMonth = day >= startDay ? month : month - 1
  const start = iso(year, startMonth, startDay)
  const [sy, sm] = parts(start)
  // Day 0 of a month is the last day of the one before.
  return [start, iso(sy, sm + 1, startDay - 1)]
}

/** The financial month `months` before (negative) or after the one that contains `date`. */
export function shiftPeriod(date: string, months: number, startDay: number): [string, string] {
  const [start] = periodOf(date, startDay)
  const [year, month] = parts(start)
  return periodOf(iso(year, month + months, startDay), startDay)
}

export function yearRange(date: string): [string, string] {
  const [year] = parts(date)
  return [`${year}-01-01`, `${year}-12-31`]
}

/** Months between two ISO dates, counting both ends' months. */
export function monthsBetween(start: string, end: string): number {
  const [sy, sm] = parts(start)
  const [ey, em] = parts(end)
  return (ey - sy) * 12 + em - sm + 1
}
