import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, addTrackingEvent, deleteTracking, fetchTracking } from '../api/client'
import type { AdDetail, Tracking, TrackingDetail, TrackingEvent, TrackingEventInput, TrackingStatus } from '../api/types'
import { TRACKING_HINTS, TRACKING_LABELS, TRACKING_STATUSES } from '../api/types'
import { formatMoney } from './AdCard'

const KEEP_STATUS = ''

export function formatDateTime(value: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('pl-PL', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function isPast(value: string | null): boolean {
  return value !== null && new Date(value).getTime() < Date.now()
}

export function TrackingPill({ tracking }: { tracking: Tracking }) {
  const showViewing = tracking.status === 'viewing_scheduled' && tracking.viewing_at
  return (
    <span className={`tracking-pill tracking-${tracking.status}`}>
      {TRACKING_LABELS[tracking.status]}
      {showViewing && ` · ${formatDateTime(tracking.viewing_at)}`}
    </span>
  )
}

export function PriceChange({ saved, current }: { saved: number | null; current: number }) {
  if (saved === null || saved === current) return null
  const difference = current - saved
  return (
    <span className={`price-change ${difference < 0 ? 'price-change-down' : 'price-change-up'}`}>
      {difference < 0 ? '↓' : '↑'} {formatMoney(Math.abs(difference))} od zapisania
    </span>
  )
}

function toLocalInputValue(value: string | null): string {
  if (!value) return ''
  return value.slice(0, 16)
}

function eventSummary(event: TrackingEvent): string[] {
  const parts: string[] = []
  if (event.viewing_at) parts.push(`termin ${formatDateTime(event.viewing_at)}`)
  if (event.rating) parts.push(`ocena ${event.rating}/5`)
  if (event.offer_amount) parts.push(`oferta ${formatMoney(event.offer_amount)}`)
  return parts
}

interface TrackingPanelProps {
  ad: AdDetail
}

export function TrackingPanel({ ad }: TrackingPanelProps) {
  const queryClient = useQueryClient()
  const { data: tracking, isLoading } = useQuery({
    queryKey: ['tracking', ad.id],
    queryFn: () => fetchTracking(ad.id),
  })

  const refreshLists = (detail: TrackingDetail | null) => {
    queryClient.setQueryData(['tracking', ad.id], detail)
    queryClient.invalidateQueries({ queryKey: ['ads'] })
    queryClient.invalidateQueries({ queryKey: ['tracked'] })
    queryClient.invalidateQueries({ queryKey: ['ad', ad.id] })
  }

  if (isLoading) return <section className="tracking-panel"><p className="detail-status">Wczytywanie statusu...</p></section>

  return (
    <section className="tracking-panel">
      <header className="tracking-header">
        <h3>Mój status</h3>
        {tracking ? <TrackingPill tracking={tracking} /> : <span className="tracking-none">nie zapisane</span>}
      </header>

      {tracking && (
        <p className="tracking-meta">
          {tracking.price_at_save !== null && <>Cena przy zapisie {formatMoney(tracking.price_at_save)} </>}
          <PriceChange saved={tracking.price_at_save} current={ad.price_value} />
          {ad.status !== 'active' && <span className="tracking-gone">Ogłoszenie zdjęte z otodom</span>}
        </p>
      )}

      <TrackingForm
        key={tracking?.updated_at ?? 'new'}
        adId={ad.id}
        tracking={tracking ?? null}
        onSaved={refreshLists}
      />

      {tracking && tracking.events.length > 0 && (
        <ol className="tracking-timeline">
          {tracking.events.map((event) => (
            <li key={event.id}>
              <div className="tracking-timeline-head">
                {event.status ? <strong>{TRACKING_LABELS[event.status]}</strong> : <strong>Notatka</strong>}
                <span>{formatDateTime(event.created_at)}{event.author ? ` · ${event.author}` : ''}</span>
              </div>
              {eventSummary(event).length > 0 && <p className="tracking-timeline-extra">{eventSummary(event).join(' · ')}</p>}
              {event.comment && <p className="tracking-timeline-comment">{event.comment}</p>}
            </li>
          ))}
        </ol>
      )}

      {tracking && <ForgetButton adId={ad.id} onDeleted={() => refreshLists(null)} />}
    </section>
  )
}

interface TrackingFormProps {
  adId: number
  tracking: TrackingDetail | null
  onSaved: (detail: TrackingDetail) => void
}

function TrackingForm({ adId, tracking, onSaved }: TrackingFormProps) {
  const [status, setStatus] = useState<TrackingStatus | typeof KEEP_STATUS>(tracking ? KEEP_STATUS : 'shortlisted')
  const [comment, setComment] = useState('')
  const [viewingAt, setViewingAt] = useState(toLocalInputValue(tracking?.viewing_at ?? null))
  const [rating, setRating] = useState<number | undefined>(undefined)
  const [offerAmount, setOfferAmount] = useState<number | undefined>(undefined)

  const effectiveStatus = status === KEEP_STATUS ? tracking?.status : status
  const needsViewing = status === 'viewing_scheduled'
  const allowsRating = effectiveStatus === 'viewed' || effectiveStatus === 'favourite'
  const allowsOffer = effectiveStatus === 'offer_made'

  const save = useMutation({
    mutationFn: () => {
      const event: TrackingEventInput = {}
      if (status !== KEEP_STATUS) event.status = status
      if (comment.trim()) event.comment = comment.trim()
      if (needsViewing && viewingAt) event.viewing_at = viewingAt
      if (allowsRating && rating) event.rating = rating
      if (allowsOffer && offerAmount) event.offer_amount = offerAmount
      return addTrackingEvent(adId, event)
    },
    onSuccess: onSaved,
  })

  const canSave =
    !save.isPending &&
    (status !== KEEP_STATUS || comment.trim().length > 0) &&
    (!needsViewing || viewingAt.length > 0)

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (canSave) save.mutate()
  }

  return (
    <form className="tracking-form" onSubmit={onSubmit}>
      <div className="tracking-status-chips">
        {tracking && (
          <button
            type="button"
            className={status === KEEP_STATUS ? 'active' : ''}
            onClick={() => setStatus(KEEP_STATUS)}
          >
            Tylko notatka
          </button>
        )}
        {TRACKING_STATUSES.map((value) => (
          <button
            key={value}
            type="button"
            className={`tracking-chip-${value}${status === value ? ' active' : ''}`}
            onClick={() => setStatus(value)}
            title={TRACKING_HINTS[value]}
          >
            {TRACKING_LABELS[value]}
          </button>
        ))}
      </div>

      {status !== KEEP_STATUS && <p className="tracking-hint">{TRACKING_HINTS[status]}</p>}

      {needsViewing && (
        <label className="filter-field">
          <span>Data i godzina oglądania</span>
          <input type="datetime-local" value={viewingAt} onChange={(event) => setViewingAt(event.target.value)} required />
        </label>
      )}

      {allowsRating && (
        <label className="filter-field">
          <span>Nasza ocena</span>
          <select value={rating ?? ''} onChange={(event) => setRating(event.target.value ? Number(event.target.value) : undefined)}>
            <option value="">{tracking?.rating ? `bez zmian (${tracking.rating}/5)` : 'bez oceny'}</option>
            {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}/5</option>)}
          </select>
        </label>
      )}

      {allowsOffer && (
        <label className="filter-field">
          <span>Kwota oferty (zł)</span>
          <input
            type="number"
            inputMode="numeric"
            value={offerAmount ?? ''}
            placeholder={tracking?.offer_amount ? String(tracking.offer_amount) : ''}
            onChange={(event) => setOfferAmount(event.target.value ? Number(event.target.value) : undefined)}
          />
        </label>
      )}

      <label className="filter-field">
        <span>Komentarz</span>
        <textarea
          value={comment}
          rows={3}
          placeholder={status === KEEP_STATUS ? 'np. dzwoniłem, nie odebrał' : 'opcjonalnie'}
          onChange={(event) => setComment(event.target.value)}
        />
      </label>

      {save.error && (
        <p className="login-error">{save.error instanceof ApiError ? save.error.detail : String(save.error)}</p>
      )}

      <button type="submit" className="primary" disabled={!canSave}>
        {save.isPending ? 'Zapisuję...' : tracking ? 'Zapisz' : 'Zapisz mieszkanie'}
      </button>
    </form>
  )
}

function ForgetButton({ adId, onDeleted }: { adId: number; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const remove = useMutation({ mutationFn: () => deleteTracking(adId), onSuccess: onDeleted })

  if (!confirming) {
    return (
      <button type="button" className="tracking-forget" onClick={() => setConfirming(true)}>
        Usuń z moich mieszkań
      </button>
    )
  }

  return (
    <p className="tracking-forget-confirm">
      Usunąć status i całą historię?
      <button type="button" className="danger" onClick={() => remove.mutate()} disabled={remove.isPending}>Tak, usuń</button>
      <button type="button" onClick={() => setConfirming(false)}>Anuluj</button>
    </p>
  )
}
