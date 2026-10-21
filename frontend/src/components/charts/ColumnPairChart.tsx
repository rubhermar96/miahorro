import { useRef, useState } from 'react'

import { compactAmount, niceTicks, scale } from '../../lib/chart'
import { formatAmount } from '../../lib/format'
import { useWidth } from '../../lib/useWidth'

export type ColumnPair = {
  key: string
  /** Shown in the tooltip: "septiembre de 2026" */
  label: string
  /** Shown under the columns: "sept" */
  tick: string
  /** Both positive */
  first: string
  second: string
}

const HEIGHT = 200
const PAD = { top: 12, right: 8, bottom: 26, left: 56 }
const MAX_BAR = 24
const GAP = 2 // surface gap between the two columns of a pair
const RADIUS = 4

/** A column with a rounded data end and a square foot on the baseline. */
function column(x: number, top: number, width: number, bottom: number): string {
  const height = bottom - top
  if (height <= 0) {
    return ''
  }
  const r = Math.min(RADIUS, width / 2, height)
  return [
    `M${x},${bottom}`,
    `V${top + r}`,
    `Q${x},${top} ${x + r},${top}`,
    `H${x + width - r}`,
    `Q${x + width},${top} ${x + width},${top + r}`,
    `V${bottom}`,
    'Z',
  ].join(' ')
}

/** Two series side by side per period (income and expenses): thin columns from one baseline, a
 * legend, and a tooltip per period by pointer or keyboard (dataviz guide). */
export function ColumnPairChart({
  pairs,
  label,
  names,
}: {
  pairs: ColumnPair[]
  label: string
  names: [string, string]
}) {
  const wrapper = useRef<HTMLDivElement>(null)
  const width = useWidth(wrapper)
  const [active, setActive] = useState<number | null>(null)
  if (pairs.length === 0) {
    return null
  }
  const highest = Math.max(...pairs.flatMap((p) => [Number(p.first), Number(p.second)]), 1)
  const ticks = niceTicks(0, highest)
  const top = ticks[ticks.length - 1] ?? highest
  const plotRight = width - PAD.right
  const plotBottom = HEIGHT - PAD.bottom
  const band = (plotRight - PAD.left) / pairs.length
  const bar = Math.max(Math.min(MAX_BAR, (band * 0.7 - GAP) / 2), 2)
  const y = (value: number) => scale(value, 0, top, plotBottom, PAD.top)
  // Every period gets a tick when there is room; otherwise every other one.
  const every = band >= 34 ? 1 : 2
  const point = active !== null ? pairs[active] : undefined

  return (
    <div className="chart" ref={wrapper}>
      <ul className="legend small" aria-label={label}>
        <li className="legend__item">
          <span className="legend__swatch chart__first" aria-hidden="true" />
          {names[0]}
        </li>
        <li className="legend__item">
          <span className="legend__swatch chart__second" aria-hidden="true" />
          {names[1]}
        </li>
      </ul>
      <svg width={width} height={HEIGHT} role="group" aria-label={label}>
        {ticks.map((tick) => (
          <g key={tick} aria-hidden="true">
            <line className="chart__grid" x1={PAD.left} x2={plotRight} y1={y(tick)} y2={y(tick)} />
            <text className="chart__axis" x={PAD.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
              {compactAmount(tick)}
            </text>
          </g>
        ))}
        {pairs.map((pair, index) => {
          const center = PAD.left + band * index + band / 2
          const left = center - bar - GAP / 2
          return (
            <g
              key={pair.key}
              className={`chart__pair ${active === index ? 'is-active' : ''}`}
              tabIndex={0}
              role="img"
              aria-label={`${pair.label}: ${names[0]} ${formatAmount(pair.first)}, ${names[1]} ${formatAmount(pair.second)}`}
              onPointerEnter={() => setActive(index)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            >
              <rect
                className="chart__hit"
                x={PAD.left + band * index}
                y={PAD.top}
                width={band}
                height={plotBottom - PAD.top}
              />
              <path
                className="chart__first"
                d={column(left, y(Number(pair.first)), bar, plotBottom)}
              />
              <path
                className="chart__second"
                d={column(center + GAP / 2, y(Number(pair.second)), bar, plotBottom)}
              />
              {index % every === 0 && (
                <text
                  className="chart__axis"
                  x={center}
                  y={HEIGHT - 6}
                  textAnchor="middle"
                  aria-hidden="true"
                >
                  {pair.tick}
                </text>
              )}
            </g>
          )
        })}
        <line
          className="chart__baseline"
          x1={PAD.left}
          x2={plotRight}
          y1={plotBottom}
          y2={plotBottom}
        />
      </svg>
      {point && active !== null && (
        <div
          className="chart__tooltip"
          role="status"
          style={{
            left: Math.min(
              Math.max(PAD.left + band * active + band / 2 - 80, 0),
              Math.max(width - 160, 0),
            ),
          }}
        >
          <span className="muted">{point.label}</span>
          <span>
            <span className="chart__key chart__first" aria-hidden="true" />
            <strong>{formatAmount(point.first)}</strong> <span className="muted">{names[0]}</span>
          </span>
          <span>
            <span className="chart__key chart__second" aria-hidden="true" />
            <strong>{formatAmount(point.second)}</strong> <span className="muted">{names[1]}</span>
          </span>
        </div>
      )}
    </div>
  )
}
