import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { DEFAULT_QUERY, fetchFacets, fromSearchParams, searchAds, toSearchParams } from './api/client'
import type { AdSearchQuery } from './api/types'
import { SCORE_FIELDS, SCORE_LABELS } from './api/types'
import { AdCard } from './components/AdCard'
import { AdDetailPanel } from './components/AdDetailPanel'
import type { DetailVariant } from './components/AdDetailPanel'
import { FilterPanel } from './components/FilterPanel'
import { MapView } from './components/MapView'
import { SavedSearches } from './components/SavedSearches'
import { StatusView } from './components/StatusView'

type AppTab = 'search' | 'status'
type ResultsView = 'grid' | 'map'
type GridDensity = 'large' | 'medium' | 'small'

const DENSITY_STORAGE_KEY = 'otodom.grid-density'

const DENSITY_OPTIONS: Array<{ value: GridDensity; label: string }> = [
  { value: 'large', label: 'Duże' },
  { value: 'medium', label: 'Średnie' },
  { value: 'small', label: 'Małe' },
]

const DENSITY_CLASS: Record<GridDensity, string> = {
  large: '',
  medium: ' results-grid-medium',
  small: ' results-grid-small',
}

function storedDensity(): GridDensity {
  const stored = window.localStorage.getItem(DENSITY_STORAGE_KEY)
  return DENSITY_OPTIONS.some((option) => option.value === stored) ? (stored as GridDensity) : 'large'
}

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
  const initialParams = new URLSearchParams(window.location.search)
  const [query, setQuery] = useState<AdSearchQuery>(() => fromSearchParams(initialParams))
  const [view, setView] = useState<ResultsView>('grid')
  const [density, setDensity] = useState<GridDensity>(storedDensity)
  const [selectedAdId, setSelectedAdId] = useState<number | null>(
    () => (initialParams.has('ad') ? Number(initialParams.get('ad')) : null),
  )
  const [detailVariant, setDetailVariant] = useState<DetailVariant>(
    () => (initialParams.get('detail') === 'full' ? 'full' : 'panel'),
  )
  const [tab, setTab] = useState<AppTab>(() => (initialParams.get('tab') === 'status' ? 'status' : 'search'))

  useEffect(() => {
    window.localStorage.setItem(DENSITY_STORAGE_KEY, density)
  }, [density])

  useEffect(() => {
    const params = toSearchParams(query)
    if (selectedAdId !== null) {
      params.set('ad', String(selectedAdId))
      params.set('detail', detailVariant)
    }
    if (tab !== 'search') {
      params.set('tab', tab)
    }
    window.history.replaceState(null, '', `${window.location.pathname}?${params}`)
  }, [query, selectedAdId, detailVariant, tab])

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

  const showFullDetail = tab === 'search' && detailVariant === 'full' && selectedAdId !== null

  const tabs = (
    <nav className="app-tabs">
      <button type="button" className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>
        Wyszukiwarka
      </button>
      <button type="button" className={tab === 'status' ? 'active' : ''} onClick={() => setTab('status')}>
        Status
      </button>
    </nav>
  )

  if (tab === 'status') {
    return (
      <div className="app app-single">
        <main className="results">
          <header className="results-toolbar">
            {tabs}
            <div className="results-count results-count-trailing">Podgląd scrapera i enrichera</div>
          </header>
          <StatusView />
        </main>
      </div>
    )
  }

  return (
    <div className={`app${showFullDetail ? ' app-full-detail' : ''}`}>
      {!showFullDetail && (
      <FilterPanel
        query={query}
        facets={facets}
        onChange={patchQuery}
        onReset={() => setQuery({ ...DEFAULT_QUERY })}
      />
      )}

      {!showFullDetail && (
      <main className="results">
        <header className="results-toolbar">
          {tabs}
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

          {view === 'grid' && (
            <label>
              Kafelki
              <select value={density} onChange={(event) => setDensity(event.target.value as GridDensity)}>
                {DENSITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          )}

          <div className="results-view-switch">
            <button type="button" className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')}>Lista</button>
            <button type="button" className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>Mapa</button>
          </div>

          <SavedSearches query={query} onApply={(saved) => setQuery({ ...DEFAULT_QUERY, ...saved })} />
        </header>

        {error && <p className="results-error">Błąd zapytania: {String(error)}</p>}

        {view === 'grid' ? (
          <div className={`results-grid${DENSITY_CLASS[density]}`}>
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
      )}

      {selectedAdId !== null && (
        <AdDetailPanel
          adId={selectedAdId}
          variant={detailVariant}
          onClose={() => {
            setSelectedAdId(null)
            setDetailVariant('panel')
          }}
          onToggleVariant={() => setDetailVariant(detailVariant === 'full' ? 'panel' : 'full')}
        />
      )}
    </div>
  )
}
