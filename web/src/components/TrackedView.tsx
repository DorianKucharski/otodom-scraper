import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { fetchTrackedAds } from '../api/client'
import type { AdSummary, TrackingStatus } from '../api/types'
import { DISMISSED_TRACKING_STATUSES, TRACKING_LABELS, TRACKING_STATUSES } from '../api/types'
import { AdCard, formatPrice } from './AdCard'
import { formatDateTime, isPast } from './TrackingPanel'

interface TrackedViewProps {
  selectedAdId: number | null
  onSelect: (adId: number) => void
}

export function TrackedView({ selectedAdId, onSelect }: TrackedViewProps) {
  const [showDismissed, setShowDismissed] = useState(false)
  const { data: ads = [], isLoading, error } = useQuery({ queryKey: ['tracked'], queryFn: () => fetchTrackedAds() })

  const viewings = useMemo(
    () => ads
      .filter((ad) => ad.tracking?.status === 'viewing_scheduled' && ad.tracking.viewing_at)
      .sort((left, right) => left.tracking!.viewing_at!.localeCompare(right.tracking!.viewing_at!)),
    [ads],
  )

  const groups = useMemo(() => {
    const byStatus = new Map<TrackingStatus, AdSummary[]>()
    for (const ad of ads) {
      if (!ad.tracking) continue
      byStatus.set(ad.tracking.status, [...(byStatus.get(ad.tracking.status) ?? []), ad])
    }
    return TRACKING_STATUSES
      .map((status) => ({ status, ads: byStatus.get(status) ?? [] }))
      .filter((group) => group.ads.length > 0)
  }, [ads])

  const dismissedCount = ads.filter((ad) => ad.tracking && DISMISSED_TRACKING_STATUSES.includes(ad.tracking.status)).length

  if (isLoading) return <p className="results-empty">Wczytywanie...</p>
  if (error) return <p className="results-error">Błąd: {String(error)}</p>
  if (ads.length === 0) {
    return (
      <p className="results-empty">
        Nic jeszcze nie zapisaliście. Otwórz ogłoszenie w wyszukiwarce i ustaw mu status.
      </p>
    )
  }

  return (
    <div className="tracked-view">
      {viewings.length > 0 && (
        <section className="tracked-viewings">
          <h3>Oglądania</h3>
          <ul>
            {viewings.map((ad) => (
              <li
                key={ad.id}
                className={isPast(ad.tracking!.viewing_at) ? 'tracked-viewing-past' : ''}
                onClick={() => onSelect(ad.id)}
              >
                <strong>{formatDateTime(ad.tracking!.viewing_at)}</strong>
                <span className="tracked-viewing-title">{ad.title}</span>
                <span className="tracked-viewing-meta">
                  {[ad.street, ad.district, ad.city].filter(Boolean).join(', ')} · {formatPrice(ad)}
                </span>
                {isPast(ad.tracking!.viewing_at) && <span className="tracked-viewing-hint">po terminie, zmień status</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {groups
        .filter((group) => showDismissed || !DISMISSED_TRACKING_STATUSES.includes(group.status))
        .map((group) => (
          <section key={group.status} className="tracked-group">
            <h3>
              <span className={`tracking-pill tracking-${group.status}`}>{TRACKING_LABELS[group.status]}</span>
              <span className="tracked-group-count">{group.ads.length}</span>
            </h3>
            <div className="results-grid results-grid-small tracked-grid">
              {group.ads.map((ad) => (
                <AdCard key={ad.id} ad={ad} selected={ad.id === selectedAdId} onSelect={onSelect} />
              ))}
            </div>
          </section>
        ))}

      {dismissedCount > 0 && (
        <button type="button" className="tracked-toggle" onClick={() => setShowDismissed(!showDismissed)}>
          {showDismissed ? 'Ukryj odrzucone i niedostępne' : `Pokaż odrzucone i niedostępne (${dismissedCount})`}
        </button>
      )}
    </div>
  )
}
