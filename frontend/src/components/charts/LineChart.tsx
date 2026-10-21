import { type KeyboardEvent, type PointerEvent, useRef, useState } from 'react'

import { compactAmount, niceTicks, scale } from '../../lib/chart'
import { formatAmount } from '../../lib/format'
import { useWidth } from '../../lib/useWidth'

export type LinePoint = {
  key: string
  /** Shown in the tooltip: "30 sept 2026" */
  label: string
  /** Shown under the axis: "sept" */
  tick: string
  value: string
}

const HEIGHT = 180
const PAD = { top: 22, right: 12, bottom: 26, left: 56 }

/** One series over time: a 2px line over a light wash, a crosshair that snaps to the nearest
 * point and a tooltip, by pointer or with the arrow keys (dataviz guide). */
export function LineChart({ points, label }: { points: LinePoint[]; label: string }) {
  const wrapper = useRef<HTMLDivElement>(null)
  const width = useWidth(wrapper)
  const [active, setActive] = useState<number | null>(null)
  if (points.length === 0) {
    return null
  }
  const values = points.map((p) => Number(p.value))
  const ticks = niceTicks(Math.min(...values), Math.max(...values))
  const low = ticks[0] ?? 0
  const high = ticks[ticks.length - 1] ?? 1
  const plotRight = width - PAD.right
  const plotBottom = HEIGHT - PAD.bottom
  const x = (index: number) =>
    points.length === 1
      ? (PAD.left + plotRight) / 2
      : scale(index, 0, points.length - 1, PAD.left, plotRight)
  const y = (value: number) => scale(value, low, high, plotBottom, PAD.top)
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
  const area = `${line} L${x(values.length - 1)},${plotBottom} L${x(0)},${plotBottom} Z`
  const last = values.length - 1
  const shown = active ?? null
  const middle = Math.floor(last / 2)
  const tickIndexes = [...new Set([0, middle, last])]

  const pick = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const position = event.clientX - box.left
    let best = 0
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(x(i) - position) < Math.abs(x(best) - position)) best = i
    }
    setActive(best)
  }

  const keys = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const step = event.key === 'ArrowLeft' ? -1 : 1
      setActive((current) => Math.min(Math.max((current ?? last) + step, 0), last))
    }
  }

  const point = shown !== null ? points[shown] : undefined
  return (
    <div className="chart" ref={wrapper}>
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={label}
        tabIndex={0}
        onPointerMove={pick}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive(last)}
        onBlur={() => setActive(null)}
        onKeyDown={keys}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="chart__grid" x1={PAD.left} x2={plotRight} y1={y(tick)} y2={y(tick)} />
            <text className="chart__axis" x={PAD.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
              {compactAmount(tick)}
            </text>
          </g>
        ))}
        {tickIndexes.map((index) => (
          <text
            key={index}
            className="chart__axis"
            x={x(index)}
            y={HEIGHT - 6}
            textAnchor={index === 0 ? 'start' : index === last ? 'end' : 'middle'}
          >
            {points[index]?.tick}
          </text>
        ))}
        <path className="chart__area" d={area} />
        <path className="chart__line" d={line} />
        {shown !== null && (
          <line
            className="chart__crosshair"
            x1={x(shown)}
            x2={x(shown)}
            y1={PAD.top}
            y2={plotBottom}
          />
        )}
        <circle
          className="chart__dot"
          cx={x(shown ?? last)}
          cy={y(values[shown ?? last] ?? 0)}
          r={4}
        />
        {shown === null && (
          <text
            className="chart__value"
            x={x(last)}
            y={y(values[last] ?? 0) - 10}
            textAnchor={points.length === 1 ? 'middle' : 'end'}
          >
            {formatAmount(points[last]?.value ?? '0')}
          </text>
        )}
      </svg>
      {point && shown !== null && (
        <div
          className="chart__tooltip"
          role="status"
          style={{
            left: Math.min(Math.max(x(shown) - 70, 0), Math.max(width - 140, 0)),
          }}
        >
          <strong>{formatAmount(point.value)}</strong>
          <span className="muted">{point.label}</span>
        </div>
      )}
    </div>
  )
}
