import type { AdSummary } from '../api/types'
import { RENOVATION_LABELS } from '../api/types'
import { ScoreBadge } from './ScoreBadge'
import { PriceChange, TrackingPill } from './TrackingPanel'

interface AdCardProps {
  ad: AdSummary
  selected: boolean
  onSelect: (adId: number) => void
}

export function formatMoney(value: number | null | undefined, suffix = 'zł'): string {
  if (value === null || value === undefined) return '-'
  return `${value.toLocaleString('pl-PL')} ${suffix}`
}

export function formatPrice(ad: Pick<AdSummary, 'price_value' | 'offer_type'>): string {
  return formatMoney(ad.price_value, ad.offer_type === 'RENT' ? 'zł/mies.' : 'zł')
}

export function formatArea(value: number | null): string {
  return value === null ? '-' : `${value.toLocaleString('pl-PL', { maximumFractionDigits: 1 })} m²`
}

export function formatFloor(floor: string | null): string {
  if (!floor) return '-'
  if (floor === 'GROUND_FLOOR') return 'parter'
  if (floor === 'CELLAR') return 'suterena'
  if (floor === 'GARRET') return 'poddasze'
  return floor.replace('FLOOR_', 'piętro ')
}

export function AdCard({ ad, selected, onSelect }: AdCardProps) {
  const evaluation = ad.evaluation

  return (
    <article
      className={`ad-card${selected ? ' ad-card-selected' : ''}`}
      onClick={() => onSelect(ad.id)}
    >
      <div className="ad-card-image">
        {ad.thumbnail ? <img src={ad.thumbnail} alt={ad.title} loading="lazy" /> : <div className="ad-card-noimage">brak zdjęć</div>}
        {evaluation?.overall_score != null && (
          <ScoreBadge label="Ocena ogólna" value={evaluation.overall_score} compact />
        )}
        {ad.tracking && <TrackingPill tracking={ad.tracking} />}
      </div>

      <div className="ad-card-body">
        <h3 className="ad-card-title">{ad.title}</h3>

        <p className="ad-card-location">
          {[ad.district, ad.city].filter(Boolean).join(', ') || 'brak lokalizacji'}
          {ad.distance_m !== null && ` · ${(ad.distance_m / 1000).toFixed(1)} km`}
        </p>

        <p className="ad-card-price">
          <strong>{formatPrice(ad)}</strong>
          <span>{formatMoney(ad.price_per_m2, 'zł/m²')}</span>
          {ad.tracking && <PriceChange saved={ad.tracking.price_at_save} current={ad.price_value} />}
        </p>

        <p className="ad-card-params">
          {formatArea(ad.area_value)} · {ad.rooms ?? '-'} pok. · {formatFloor(ad.floor)}
          {ad.building_year ? ` · ${ad.building_year}` : ''} · {ad.features_count} cech
        </p>

        {ad.tracking?.last_comment && (
          <p className="ad-card-note">
            {ad.tracking.last_comment}
            {ad.tracking.updated_by && <span> · {ad.tracking.updated_by}</span>}
          </p>
        )}

        {evaluation?.summary && <p className="ad-card-summary">{evaluation.summary}</p>}

        {evaluation && (
          <div className="ad-card-scores">
            <ScoreBadge label="Wykończenie" value={evaluation.finish_quality_score} />
            <ScoreBadge label="Gotowość" value={evaluation.move_in_readiness_score} />
            <ScoreBadge label="Opłacalność" value={evaluation.value_for_money_score} />
            <ScoreBadge label="Zdjęcia" value={evaluation.photo_trust_score} />
          </div>
        )}

        {evaluation?.renovation_needed && (
          <p className="ad-card-renovation">{RENOVATION_LABELS[evaluation.renovation_needed] ?? evaluation.renovation_needed}</p>
        )}

        {evaluation && evaluation.concerns.length > 0 && (
          <ul className="ad-card-concerns">
            {evaluation.concerns.slice(0, 3).map((concern) => (
              <li key={concern}>{concern}</li>
            ))}
          </ul>
        )}
      </div>
    </article>
  )
}
