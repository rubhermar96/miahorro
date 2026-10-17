/** A ratio against a limit: one hue for the filled part over a lighter track of the same hue.
 * The value is also written next to it, so colour is never the only cue. */
export function Meter({
  value,
  max = 100,
  label,
  marker,
  markerLabel,
}: {
  value: number
  max?: number
  label: string
  /** A reference on the track (e.g. the target savings rate). */
  marker?: number
  markerLabel?: string
}) {
  const share = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0
  const markerShare = marker !== undefined && max > 0 ? Math.min(marker / max, 1) : undefined
  return (
    <div
      className="meter"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(Math.min(Math.max(value, 0), max))}
    >
      <div className="meter__fill" style={{ width: `${share * 100}%` }} />
      {markerShare !== undefined && (
        <div
          className="meter__marker"
          style={{ left: `${markerShare * 100}%` }}
          title={markerLabel}
          aria-hidden="true"
        />
      )}
    </div>
  )
}
