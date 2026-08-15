import type {
  AdDetail,
  AdSearchQuery,
  AdSearchResponse,
  DistrictStats,
  Facets,
  SavedSearch,
} from './types'

const API_BASE = '/api'

export const DEFAULT_QUERY: AdSearchQuery = {
  voivodeships: [],
  cities: [],
  districts: [],
  exclude_ground_floor: false,
  exclude_top_floor: false,
  building_types: [],
  building_materials: [],
  building_heating: [],
  markets: [],
  advertiser_types: [],
  property_types: [],
  property_conditions: [],
  object_types: [],
  offer_types: [],
  statuses: ['active'],
  features: [],
  feature_match: 'all',
  excluded_features: [],
  require_evaluation: false,
  renovation_needed: [],
  style_tags: [],
  attributes: [],
  sort: 'created_at',
  direction: 'desc',
  limit: 50,
  offset: 0,
}

const NUMERIC_FIELDS = new Set([
  'latitude',
  'longitude',
  'radius_m',
  'min_price',
  'max_price',
  'min_price_per_m2',
  'max_price_per_m2',
  'max_rent',
  'min_area',
  'max_area',
  'min_rooms',
  'max_rooms',
  'min_floor',
  'max_floor',
  'min_building_year',
  'max_building_year',
  'min_features_count',
  'min_overall_score',
  'min_finish_quality_score',
  'min_freshness_score',
  'min_move_in_readiness_score',
  'min_layout_score',
  'min_natural_light_score',
  'min_building_condition_score',
  'min_location_score',
  'min_value_for_money_score',
  'min_photo_trust_score',
])

export function toSearchParams(query: AdSearchQuery): URLSearchParams {
  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, String(item)))
    } else {
      params.append(key, String(value))
    }
  }

  return params
}

export function fromSearchParams(params: URLSearchParams): AdSearchQuery {
  const query: Record<string, unknown> = { ...DEFAULT_QUERY }

  for (const key of new Set(params.keys())) {
    const values = params.getAll(key)
    const fallback = (DEFAULT_QUERY as unknown as Record<string, unknown>)[key]

    if (Array.isArray(fallback)) {
      query[key] = values
    } else if (typeof fallback === 'boolean') {
      query[key] = values[0] === 'true'
    } else if (typeof fallback === 'number' || NUMERIC_FIELDS.has(key)) {
      query[key] = Number(values[0])
    } else {
      query[key] = values[0]
    }
  }

  return query as unknown as AdSearchQuery
}


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${detail}`)
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

export function searchAds(query: AdSearchQuery): Promise<AdSearchResponse> {
  return request<AdSearchResponse>(`/ads?${toSearchParams(query)}`)
}

export function fetchAd(adId: number): Promise<AdDetail> {
  return request<AdDetail>(`/ads/${adId}`)
}

export function fetchFacets(): Promise<Facets> {
  return request<Facets>('/facets')
}

export function fetchDistrictStats(city?: string): Promise<DistrictStats[]> {
  const suffix = city ? `?city=${encodeURIComponent(city)}` : ''
  return request<DistrictStats[]>(`/stats/districts${suffix}`)
}

export function fetchSavedSearches(): Promise<SavedSearch[]> {
  return request<SavedSearch[]>('/saved-searches')
}

export function createSavedSearch(name: string, query: AdSearchQuery): Promise<SavedSearch> {
  return request<SavedSearch>('/saved-searches', {
    method: 'POST',
    body: JSON.stringify({ name, query }),
  })
}

export function deleteSavedSearch(savedSearchId: number): Promise<void> {
  return request<void>(`/saved-searches/${savedSearchId}`, { method: 'DELETE' })
}
