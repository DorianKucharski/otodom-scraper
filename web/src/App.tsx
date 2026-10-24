import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { DEFAULT_QUERY, fetchFacets, fromSearchParams, searchAds, toSearchParams } from './api/client'
import type { AdSearchQuery } from './api/types'
import { SCORE_FIELDS, SCORE_LABELS } from './api/types'
import { AdCard } from './components/AdCard'
import { AdDetailPanel } from './components/AdDetailPanel'
import { AssistantPanel } from './components/AssistantPanel'
import { SessionBadge } from './components/AuthGate'
import type { DetailVariant } from './components/AdDetailPanel'
import { FilterPanel } from './components/FilterPanel'
import { MapView } from './components/MapView'
import { SavedSearches } from './components/SavedSearches'
import { StatusView } from './components/StatusView'
import { TrackedView } from './components/TrackedView'

type AppTab = 'search' | 'tracked' | 'status'

const APP_TABS: Array<{ value: AppTab; label: string }> = [
  { value: 'search', label: 'Wyszukiwarka' },
  { value: 'tracked', label: 'Moje mieszkania' },
  { value: 'status', label: 'Status' },
]
type ResultsView = 'grid' | 'map'
type GridDensity = 'large' | 'medium' | 'small'

const DENSITY_STORAGE_KEY = 'otodom.grid-density'
const ASSISTANT_STORAGE_KEY = 'otodom.assistant-open'
const SEARCH_DEBOUNCE_MS = 400

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

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

function storedAssistantOpen(): boolean {
  try {
    return window.localStorage.getItem(ASSISTANT_STORAGE_KEY) !== 'false'
  } catch {
    return true
  }
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
  { value: 'days_on_market', label: 'Czas na rynku' },
  { value: 'price_vs_comparables_pct', label: 'Cena wobec okolicy' },
  { value: 'price_change_pct', label: 'Zmiana ceny' },
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
  const [tab, setTab] = useState<AppTab>(
    () => APP_TABS.find((option) => option.value === initialParams.get('tab'))?.value ?? 'search',
  )
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(storedAssistantOpen)

  useEffect(() => {
    try {
      window.localStorage.setItem(ASSISTANT_STORAGE_KEY, String(assistantOpen))
    } catch {
      return
    }
  }, [assistantOpen])

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
  const searchedQuery = useDebounced(query, SEARCH_DEBOUNCE_MS)
  const { data, isFetching, error } = useQuery({
    queryKey: ['ads', toSearchParams(searchedQuery).toString()],
    queryFn: () => searchAds(searchedQuery),
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

  const showFullDetail = tab !== 'status' && detailVariant === 'full' && selectedAdId !== null

  const tabs = (
    <nav className="app-tabs">
      {APP_TABS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={tab === option.value ? 'active' : ''}
          onClick={() => setTab(option.value)}
        >
          {option.label}
        </button>
      ))}
      <SessionBadge />
    </nav>
  )

  const detailPanel = selectedAdId !== null && (
    <AdDetailPanel
      adId={selectedAdId}
      variant={detailVariant}
      onClose={() => {
        setSelectedAdId(null)
        setDetailVariant('panel')
      }}
      onToggleVariant={() => setDetailVariant(detailVariant === 'full' ? 'panel' : 'full')}
    />
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

  if (tab === 'tracked') {
    return (
      <div className={`app app-tracked${showFullDetail ? ' app-full-detail' : ''}`}>
        {!showFullDetail && (
          <main className="results">
            <header className="results-toolbar">
              {tabs}
            </header>
            <TrackedView selectedAdId={selectedAdId} onSelect={setSelectedAdId} />
          </main>
        )}
        {detailPanel}
      </div>
    )
  }

  return (
    <div className={`app${showFullDetail ? ' app-full-detail' : ''}${filtersOpen ? ' app-filters-open' : ''}`}>
      {!showFullDetail && (
      <FilterPanel
        query={query}
        facets={facets}
        onChange={patchQuery}
        onReset={() => setQuery({ ...DEFAULT_QUERY })}
        onClose={() => setFiltersOpen(false)}
      />
      )}

      {!showFullDetail && (
      <main className="results">
        <header className="results-toolbar">
          {tabs}
          <button type="button" className="mobile-only" onClick={() => setFiltersOpen(true)}>Filtry</button>
          <button
            type="button"
            className={assistantOpen ? 'active assistant-toggle' : 'assistant-toggle'}
            onClick={() => setAssistantOpen(!assistantOpen)}
          >
            Asystent AI
          </button>
          <div className="results-count">
            {isFetching || searchedQuery !== query ? 'Szukam...' : `${(data?.total ?? 0).toLocaleString('pl-PL')} ogłoszeń`}
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

        <div className="results-scroll" hidden={view !== 'grid'}>
          <AssistantPanel
            hidden={!assistantOpen}
            query={query}
            onApplyQuery={setQuery}
            selectedAdId={selectedAdId}
            onSelect={setSelectedAdId}
          />
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
        </div>
        {view === 'map' && <MapView ads={data?.items ?? []} onSelect={setSelectedAdId} />}

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

      {detailPanel}
    </div>
  )
}
