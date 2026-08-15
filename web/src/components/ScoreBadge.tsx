interface ScoreBadgeProps {
  label: string
  value: number | null
  compact?: boolean
}

export function scoreClass(value: number | null): string {
  if (value === null) return 'score score-unknown'
  if (value <= 3) return 'score score-bad'
  if (value <= 5) return 'score score-weak'
  if (value <= 7) return 'score score-ok'
  if (value <= 8) return 'score score-good'
  return 'score score-great'
}

export function ScoreBadge({ label, value, compact = false }: ScoreBadgeProps) {
  return (
    <span className={scoreClass(value)} title={label}>
      {!compact && <span className="score-label">{label}</span>}
      <span className="score-value">{value ?? '?'}</span>
    </span>
  )
}

interface ScoreBarProps {
  label: string
  value: number | null
}

export function ScoreBar({ label, value }: ScoreBarProps) {
  return (
    <div className="score-bar">
      <span className="score-bar-label">{label}</span>
      <span className="score-bar-track">
        <span className={`score-bar-fill ${scoreClass(value)}`} style={{ width: `${(value ?? 0) * 10}%` }} />
      </span>
      <span className="score-bar-value">{value ?? '-'}</span>
    </div>
  )
}
