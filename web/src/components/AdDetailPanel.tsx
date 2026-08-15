import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { fetchAd } from '../api/client'
import { RENOVATION_LABELS, SCORE_FIELDS, SCORE_LABELS } from '../api/types'
import { formatArea, formatFloor, formatMoney } from './AdCard'
import { ScoreBar } from './ScoreBadge'

export type DetailVariant = 'panel' | 'full'

interface AdDetailPanelProps {
  adId: number
  variant: DetailVariant
  onClose: () => void
  onToggleVariant: () => void
}

export function AdDetailPanel({ adId, variant, onClose, onToggleVariant }: AdDetailPanelProps) {
  const [activeImage, setActiveImage] = useState(0)
  const { data: ad, isLoading, error } = useQuery({
    queryKey: ['ad', adId],
    queryFn: () => fetchAd(adId),
  })

  const className = variant === 'full' ? 'detail-panel detail-panel-full' : 'detail-panel'

  if (isLoading) return <aside className={className}><p className="detail-status">Wczytywanie...</p></aside>
  if (error || !ad) {
    return (
      <aside className={className}>
        <p className="detail-status">Nie udało się wczytać ogłoszenia.</p>
        <button type="button" onClick={onClose}>Zamknij</button>
      </aside>
    )
  }

  const evaluation = ad.evaluation
  const image = ad.images[Math.min(activeImage, Math.max(ad.images.length - 1, 0))]

  return (
    <aside className={className}>
      <header className="detail-header">
        <h2>{ad.title}</h2>
        <div className="detail-header-actions">
          <button type="button" onClick={onToggleVariant}>
            {variant === 'full' ? 'Wróć do wyników' : 'Pełny widok'}
          </button>
          <button type="button" onClick={onClose}>×</button>
        </div>
      </header>

      <div className="detail-body">
      <div className="detail-column">
      {image && (
        <div className="detail-gallery">
          <img src={image.large} alt={ad.title} />
          <div className="detail-thumbnails">
            {ad.images.map((galleryImage, index) => (
              <img
                key={galleryImage.position}
                src={galleryImage.thumbnail}
                alt=""
                className={index === activeImage ? 'active' : ''}
                onClick={() => setActiveImage(index)}
              />
            ))}
          </div>
        </div>
      )}

      <section className="detail-summary">
        <p className="detail-price">
          <strong>{formatMoney(ad.price_value)}</strong>
          <span>{formatMoney(ad.price_per_m2, 'zł/m²')}</span>
          {ad.rent_value ? <span>czynsz {formatMoney(ad.rent_value)}</span> : null}
        </p>
        <p className="detail-location">
          {[ad.street, ad.district, ad.city, ad.province].filter(Boolean).join(', ')}
        </p>
        {ad.market_stats?.median_price_per_m2 && (
          <p className="detail-market">
            Mediana {ad.market_stats.is_city_level ? 'w mieście' : 'w dzielnicy'}:{' '}
            {formatMoney(ad.market_stats.median_price_per_m2, 'zł/m²')} ({ad.market_stats.ad_count} ogłoszeń)
          </p>
        )}
        <a className="detail-link" href={ad.url} target="_blank" rel="noreferrer">Otwórz w otodom</a>
      </section>

      {evaluation && (
        <section className="detail-evaluation">
          <h3>Ocena AI</h3>
          {evaluation.summary && <p className="detail-ai-summary">{evaluation.summary}</p>}

          <div className="detail-scores">
            {SCORE_FIELDS.map((field) => (
              <ScoreBar key={field} label={SCORE_LABELS[field]} value={evaluation[field]} />
            ))}
          </div>

          <p className="detail-tags">
            {evaluation.renovation_needed && (
              <span className="tag">{RENOVATION_LABELS[evaluation.renovation_needed] ?? evaluation.renovation_needed}</span>
            )}
            {evaluation.style_tag && <span className="tag">{evaluation.style_tag}</span>}
            <span className="tag">{evaluation.images_evaluated} zdjęć ocenionych</span>
          </p>

          {evaluation.strengths.length > 0 && (
            <>
              <h4>Mocne strony</h4>
              <ul className="detail-list detail-strengths">
                {evaluation.strengths.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </>
          )}

          {evaluation.concerns.length > 0 && (
            <>
              <h4>Zastrzeżenia</h4>
              <ul className="detail-list detail-concerns">
                {evaluation.concerns.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </>
          )}

          {Object.keys(evaluation.attributes).length > 0 && (
            <>
              <h4>Atrybuty odczytane przez AI</h4>
              <dl className="detail-attributes">
                {Object.entries(evaluation.attributes).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      )}

      </div>

      <div className="detail-column">
      <section className="detail-parameters">
        <h3>Parametry</h3>
        <dl className="detail-attributes">
          <div><dt>Powierzchnia</dt><dd>{formatArea(ad.area_value)}</dd></div>
          <div><dt>Pokoje</dt><dd>{ad.rooms ?? '-'}</dd></div>
          <div><dt>Piętro</dt><dd>{formatFloor(ad.floor)} z {ad.building_number_of_floors ?? '-'}</dd></div>
          <div><dt>Rok budowy</dt><dd>{ad.building_year ?? '-'}</dd></div>
          <div><dt>Typ budynku</dt><dd>{ad.building_type ?? '-'}</dd></div>
          <div><dt>Materiał</dt><dd>{ad.building_material ?? '-'}</dd></div>
          <div><dt>Ogrzewanie</dt><dd>{ad.building_heating ?? '-'}</dd></div>
          <div><dt>Rynek</dt><dd>{ad.market ?? '-'}</dd></div>
          <div><dt>Ogłaszający</dt><dd>{ad.advertiser_type ?? '-'}</dd></div>
          <div><dt>Stan wg serwisu</dt><dd>{ad.property_condition ?? '-'}</dd></div>
        </dl>
      </section>

      {Object.keys(ad.screening_attributes).length > 0 && (
        <section className="detail-parameters">
          <h3>Fakty wyciągnięte z opisu</h3>
          <dl className="detail-attributes">
            {Object.entries(ad.screening_attributes).map(([key, value]) => (
              <div key={key}><dt>{key}</dt><dd>{value}</dd></div>
            ))}
          </dl>
        </section>
      )}

      <section className="detail-parameters">
        <h3>Cechy i wyposażenie</h3>
        {Object.entries(ad.feature_groups).map(([group, values]) => (
          values.length > 0 && (
            <p key={group} className="detail-feature-group">
              <strong>{group}:</strong> {values.join(', ')}
            </p>
          )
        ))}
      </section>

      {ad.description && (
        <section className="detail-parameters">
          <h3>Opis</h3>
          <p className="detail-description">{ad.description}</p>
        </section>
      )}
      </div>
      </div>
    </aside>
  )
}
