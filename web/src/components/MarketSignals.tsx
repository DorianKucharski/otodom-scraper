import { useQuery } from '@tanstack/react-query'

import { fetchAdHistory } from '../api/client'
import type { AdSummary, MarketSignals } from '../api/types'
import { LOCATION_FLAG_LABELS } from '../api/types'

const LONG_ON_MARKET_DAYS = 90
const NOTABLE_ON_MARKET_DAYS = 45
const NOTABLE_COMPARABLE_PCT = 10
const STALE_AFTER_DAYS = 45
const DAY_MS = 24 * 60 * 60 * 1000

function money(value: number | null | undefined, suffix = 'zł'): string {
  if (value === null || value === undefined) return '-'
  return `${value.toLocaleString('pl-PL')} ${suffix}`
}

function percent(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}%`
}

export function formatDuration(days: number): string {
  if (days >= 365) {
    const years = days / 365
    return `${years.toLocaleString('pl-PL', { maximumFractionDigits: 1 })} roku`
  }
  if (days >= 60) return `${Math.round(days / 30)} mies.`
  if (days === 1) return '1 dzień'
  return `${days} dni`
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString('pl-PL') : '-'
}

function transactionsTitle(signals: MarketSignals): string {
  return (
    `Mediana ${money(signals.transactions_median_price_per_m2, 'zł/m²')} z ${signals.transactions_count} sprzedaży lokali ` +
    `z Rejestru Cen Nieruchomości z ostatnich 2 lat (metraż ±35%, do ` +
    `${((signals.transactions_radius_m ?? 0) / 1000).toLocaleString('pl-PL')} km). To ceny transakcyjne, nie ofertowe. ` +
    `Środkowa połowa: ${money(signals.transactions_p25_price_per_m2)} – ${money(signals.transactions_p75_price_per_m2, 'zł/m²')}.`
  )
}

function comparablesTitle(signals: MarketSignals): string {
  return (
    `Mediana ${money(signals.comparables_median_price_per_m2, 'zł/m²')} z ${signals.comparables_count} podobnych ofert ` +
    `(metraż ±35%, do ${((signals.comparables_radius_m ?? 0) / 1000).toLocaleString('pl-PL')} km od pinezki, ` +
    `aktywne i zdjęte w ostatnim półroczu). Środkowa połowa: ${money(signals.comparables_p25_price_per_m2)} – ` +
    `${money(signals.comparables_p75_price_per_m2, 'zł/m²')}.`
  )
}

interface SignalChipsProps {
  ad: Pick<AdSummary, 'market_signals' | 'last_checked_at'>
}

export function SignalChips({ ad }: SignalChipsProps) {
  const signals = ad.market_signals
  const chips: Array<{ key: string; label: string; tone: string; title: string }> = []

  const uncheckedDays = ad.last_checked_at
    ? Math.floor((Date.now() - new Date(ad.last_checked_at).getTime()) / DAY_MS)
    : null
  if (uncheckedDays !== null && uncheckedDays > STALE_AFTER_DAYS) {
    chips.push({
      key: 'stale',
      label: `⚠ niesprawdzane od ${formatDuration(uncheckedDays)}`,
      tone: 'warn',
      title:
        `Scraper ostatnio widział to ogłoszenie ${formatDate(ad.last_checked_at)}. ` +
        'Odświeża tylko obszar ustawiony w docker-compose, więc ogłoszenie mogło już zniknąć z otodom.',
    })
  }

  if (!signals) {
    return chips.length ? <ChipList chips={chips} /> : null
  }

  if (signals.days_on_market >= NOTABLE_ON_MARKET_DAYS || signals.listings_count > 1) {
    chips.push({
      key: 'days',
      label: `na rynku ${formatDuration(signals.days_on_market)}`
        + (signals.listings_count > 1 ? ` · ${signals.listings_count} ogł.` : ''),
      tone: signals.days_on_market >= LONG_ON_MARKET_DAYS ? 'warn' : 'neutral',
      title:
        `Ten sam lokal ogłaszany od ${formatDate(signals.first_listed_at)}` +
        (signals.listings_count > 1
          ? `, ${signals.listings_count} ogłoszeń od ${signals.advertisers_count} ogłoszeniodawców.`
          : '.'),
    })
  }

  if (signals.price_change_pct) {
    chips.push({
      key: 'trend',
      label: `cena ${percent(signals.price_change_pct)}`,
      tone: signals.price_change_pct > 0 ? 'bad' : 'good',
      title: `Pierwsza znana cena tego lokalu: ${money(signals.first_price)}.`,
    })
  }

  if (signals.price_vs_comparables_pct !== null) {
    const value = signals.price_vs_comparables_pct
    chips.push({
      key: 'comparables',
      label: `${percent(value)} vs okolica`,
      tone: value <= -NOTABLE_COMPARABLE_PCT ? 'good' : value >= NOTABLE_COMPARABLE_PCT ? 'bad' : 'neutral',
      title: comparablesTitle(signals),
    })
  }

  if (signals.price_vs_transactions_pct !== null) {
    const value = signals.price_vs_transactions_pct
    chips.push({
      key: 'transactions',
      label: `${percent(value)} vs transakcje`,
      tone: value <= -NOTABLE_COMPARABLE_PCT ? 'good' : value >= NOTABLE_COMPARABLE_PCT ? 'bad' : 'neutral',
      title: transactionsTitle(signals),
    })
  }

  for (const flag of signals.location_flags) {
    const nearBorder = flag === 'near_city_border'
    chips.push({
      key: flag,
      label: nearBorder
        ? `${signals.city_border_distance_m} m od granicy miasta`
        : `⚠ ${LOCATION_FLAG_LABELS[flag] ?? flag}`,
      tone: nearBorder && signals.location_flags.length === 1 ? 'neutral' : 'warn',
      title: signals.location_notes.join('\n'),
    })
  }

  if (chips.length === 0) return null

  return <ChipList chips={chips} />
}

function ChipList({ chips }: { chips: Array<{ key: string; label: string; tone: string; title: string }> }) {
  return (
    <p className="signal-chips">
      {chips.map((chip) => (
        <span key={chip.key} className={`signal-chip signal-${chip.tone}`} title={chip.title}>
          {chip.label}
        </span>
      ))}
    </p>
  )
}

interface MarketHistoryProps {
  adId: number
  signals: MarketSignals | null
}

export function MarketHistory({ adId, signals }: MarketHistoryProps) {
  const { data: history } = useQuery({
    queryKey: ['ad-history', adId],
    queryFn: () => fetchAdHistory(adId),
    enabled: signals !== null,
  })

  if (!signals) return null

  return (
    <section className="detail-parameters market-history">
      <h3>Historia ogłoszenia i rynek</h3>

      {signals.location_notes.length > 0 && (
        <ul className="detail-list market-warnings">
          {signals.location_notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      )}

      <dl className="detail-attributes">
        <div>
          <dt>Na rynku</dt>
          <dd>
            {formatDuration(signals.days_on_market)}, od {formatDate(signals.first_listed_at)}
          </dd>
        </div>
        <div>
          <dt>Ogłoszenia lokalu</dt>
          <dd>{signals.listings_count} (ogłoszeniodawców: {signals.advertisers_count})</dd>
        </div>
        <div>
          <dt>Pierwsza znana cena</dt>
          <dd>
            {money(signals.first_price)}
            {signals.price_change_pct ? ` (teraz ${percent(signals.price_change_pct)})` : ''}
          </dd>
        </div>
        <div>
          <dt>Najniższa / najwyższa</dt>
          <dd>{money(signals.lowest_price)} / {money(signals.highest_price)}</dd>
        </div>
        {signals.comparables_median_price_per_m2 !== null && (
          <div>
            <dt>Podobne w okolicy</dt>
            <dd title={comparablesTitle(signals)}>
              mediana {money(signals.comparables_median_price_per_m2, 'zł/m²')}
              {signals.price_vs_comparables_pct !== null && `, ta oferta ${percent(signals.price_vs_comparables_pct)}`}
              {` (${signals.comparables_count} ofert do ${((signals.comparables_radius_m ?? 0) / 1000).toLocaleString('pl-PL')} km)`}
            </dd>
          </div>
        )}
        {signals.transactions_median_price_per_m2 !== null && (
          <div>
            <dt>Transakcje (RCN)</dt>
            <dd title={transactionsTitle(signals)}>
              mediana {money(signals.transactions_median_price_per_m2, 'zł/m²')}
              {signals.price_vs_transactions_pct !== null && `, ta oferta ${percent(signals.price_vs_transactions_pct)}`}
              {` (${signals.transactions_count} sprzedaży do ${((signals.transactions_radius_m ?? 0) / 1000).toLocaleString('pl-PL')} km)`}
            </dd>
          </div>
        )}
        {(signals.pin_city_name || signals.pin_gmina_name) && (
          <div>
            <dt>Pinezka leży w</dt>
            <dd>
              {signals.pin_city_name ?? `gmina ${signals.pin_gmina_name}`}
              {signals.city_border_distance_m !== null && `, ${signals.city_border_distance_m} m od granicy miasta`}
            </dd>
          </div>
        )}
      </dl>

      {history && history.listings.length > 1 && (
        <table className="history-table">
          <thead>
            <tr>
              <th>Wystawione</th>
              <th>Ogłoszeniodawca</th>
              <th>Cena</th>
              <th>Metraż</th>
              <th>Miejsce</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {history.listings.map((listing) => (
              <tr key={listing.id} className={listing.id === adId ? 'current' : ''}>
                <td><a href={listing.url} target="_blank" rel="noreferrer">{formatDate(listing.created_at)}</a></td>
                <td>{listing.advertiser_name ?? listing.advertiser_type ?? '-'}</td>
                <td>{money(listing.price_value)}</td>
                <td>{listing.area_value ? `${listing.area_value.toLocaleString('pl-PL')} m²` : '-'}</td>
                <td>{[listing.district, listing.city].filter(Boolean).join(', ') || '-'}</td>
                <td>{listing.status === 'active' ? 'aktywne' : `zdjęte, widziane ${formatDate(listing.last_seen_at)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {history && history.prices.length > 1 && (
        <ul className="detail-list price-timeline">
          {history.prices.map((price, index) => (
            <li key={`${price.ad_id}-${index}`}>
              {formatDate(price.observed_at)}: {money(price.price_value)}
              {price.status && price.status !== 'active' ? ` (${price.status})` : ''}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
