import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { DEFAULT_QUERY, fetchFacets, fromSearchParams, searchAds, toSearchParams } from './api/client'
import type { AdSearchQuery } from './api/types'
import { SCORE_FIELDS, SCORE_LABELS } from './api/types'
import { AdCard } from './components/AdCard'
import { AdDetailPanel } from './components/AdDetailPanel'
import { FilterPanel } from './components/FilterPanel'
import { MapView } from './components/MapView'
import { SavedSearches } from './components/SavedSearches'

type ResultsView = 'grid' | 'map'

const SORT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'created_at', label: 'Data dodania' },
  { value: 'modified_at', label: 'Data aktualizacji' },
  { value: 'price_value', label: 'Cena' },
  { value: 'price_per_m2', label: 'Cena za metr' },
  { value: 'area_value', label: 'Powierzchnia' },
  { value: 'flat_number_of_rooms', label: 'Liczba pokoi' },
  { value: 'building_year', label: 'Rok budowy' },
  { value: 'features_count', label: 'Liczba cech' },
  { value: 'distance', label: 'Odległość od punktu' },
  ...SCORE_FIELDS.map((field) => ({ value: field, label: `AI: ${SCORE_LABELS[field]}` })),
]

export function App() {
  const [query, setQuery] = useState<AdSearchQuery>(() => fromSearchParams(new URLSearchParams(window.location.search)))
  const [view, setView] = useState<ResultsView>('grid')
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null)

  useEffect(() => {
    const params = toSearchParams(query)
    window.history.replaceState(null, '', `${window.location.pathname}?${params}`)
  }, [query])

  const { data: facets } = useQuery({ queryKey: ['facets'], queryFn: fetchFacets, staleTime: 5 * 60 * 1000 })
  const { data, isFetching, error } = useQuery({
    queryKey: ['ads', toSearchParams(query).toString()],
    queryFn: () => searchAds(query),
    placeholderData: (previous) => previous,
  })

  const patchQuery = useCallback((patch: Partial<AdSearchQuery>) => {
    setQuery((current) => ({ ...current, ...patch, offset: patch.offset ?? 0 }))
  }, [])

  const page = useMemo(() => Math.floor(query.offset / query.limit) + 1, [query.offset, query.limit])
  const pageCount = useMemo(
    () => (data ? Math.max(Math.ceil(data.total / query.limit), 1) : 1),
    [data, query.limit],
  )

  return (
    <div className="app">
      <FilterPanel
        query={query}
        facets={facets}
        onChange={patchQuery}
        onReset={() => setQuery({ ...DEFAULT_QUERY })}
      />

      <main className="results">
        <header className="results-toolbar">
          <div className="results-count">
            {isFetching ? 'Szukam...' : `${data?.total ?? 0} ogłoszeń`}
          </div>

          <label>
            Sortuj
            <select value={query.sort} onChange={(event) => patchQuery({ sort: event.target.value })}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            Kierunek
            <select
              value={query.direction}
              onChange={(event) => patchQuery({ direction: event.target.value as AdSearchQuery['direction'] })}
            >
              <option value="desc">malejąco</option>
              <option value="asc">rosnąco</option>
            </select>
          </label>

          <label>
            Na stronie
            <select value={query.limit} onChange={(event) => patchQuery({ limit: Number(event.target.value) })}>
              {[25, 50, 100, 200].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>

          <div className="results-view-switch">
            <button type="button" className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')}>Lista</button>
            <button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>Mapa</button>
          </div>

          <SavedSearches query={query} onApply={(saved) => setQuery({ ...DEFAULT_QUERY, ...saved })} />
        </header>

        {error && <p className="results-error">Błąd zapytania: {String(error)}</p>}

        {view === 'grid' ? (
          <div className="results-grid">
            {data?.items.map((ad) => (
              <AdCard
                key={ad.id}
                ad={ad}
                selected={ad.id === selectedAdId}
                onSelect={setSelectedAdId}
              />
            ))}
            {data && data.items.length === 0 && <p className="results-empty">Brak ogłoszeń dla tych filtrów.</p>}
          </div>
        ) : (
          <MapView ads={data?.items ?? []} onSelect={setSelectedAdId} />
        )}

        <footer className="results-pagination">
          <button
            type="button"
            disabled={query.offset === 0}
            onClick={() => setQuery({ ...query, offset: Math.max(query.offset - query.limit, 0) })}
          >
            Poprzednia
          </button>
          <span>{page} z {pageCount}</span>
          <button
            type="button"
            disabled={!data || query.offset + query.limit >= data.total}
            onClick={() => setQuery({ ...query, offset: query.offset + query.limit })}
          >
            Następna
          </button>
        </footer>
      </main>

      {selectedAdId !== null && (
        <AdDetailPanel adId={selectedAdId} onClose={() => setSelectedAdId(null)} />
      )}
    </div>
  )
}
