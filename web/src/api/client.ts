import type {
  AdDetail,
  AssistantInterpretResponse,
  AssistantPlan,
  AssistantRankResponse,
  AssistantStatus,
  EvaluationRequest,
  AdSearchQuery,
  AdSearchResponse,
  DistrictStats,
  Facets,
  ListingHistory,
  SavedSearch,
  ServiceLogs,
  ServiceStatus,
  Session,
  TrackingDetail,
  TrackingEventInput,
  TrackingStatus,
  AdSummary,
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
  price_trends: [],
  excluded_location_flags: [],
  tracking_statuses: [],
  hide_dismissed: true,
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
  'min_days_on_market',
  'max_days_on_market',
  'min_listings_count',
  'max_price_vs_comparables_pct',
  'min_price_vs_comparables_pct',
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

export const UNAUTHORIZED_EVENT = 'otodom:unauthorized'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...init,
  })

  if (!response.ok) {
    const body = await response.text()
    let detail = body
    try {
      const parsed = JSON.parse(body)
      if (typeof parsed.detail === 'string') detail = parsed.detail
    } catch {
      detail = body || response.statusText
    }
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(response.status, detail)
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

export function searchAds(query: AdSearchQuery): Promise<AdSearchResponse> {
  return request<AdSearchResponse>(`/ads?${toSearchParams(query)}`)
}

export function fetchAd(adId: number): Promise<AdDetail> {
  return request<AdDetail>(`/ads/${adId}`)
}

export function fetchAdHistory(adId: number): Promise<ListingHistory> {
  return request<ListingHistory>(`/ads/${adId}/history`)
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

export function fetchServices(): Promise<ServiceStatus[]> {
  return request<ServiceStatus[]>('/services')
}

export function fetchServiceLogs(
  service: string,
  limit: number,
  minLevel?: string,
  search?: string,
): Promise<ServiceLogs> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (minLevel) params.set('min_level', minLevel)
  if (search) params.set('search', search)
  return request<ServiceLogs>(`/services/${service}/logs?${params}`)
}

export function fetchSession(): Promise<Session> {
  return request<Session>('/auth/me')
}

export function login(name: string, password: string): Promise<Session> {
  return request<Session>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ name, password }),
  })
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function fetchTrackedAds(statuses: TrackingStatus[] = []): Promise<AdSummary[]> {
  const params = new URLSearchParams()
  statuses.forEach((status) => params.append('statuses', status))
  const suffix = statuses.length > 0 ? `?${params}` : ''
  return request<AdSummary[]>(`/tracking${suffix}`)
}

export function fetchTracking(adId: number): Promise<TrackingDetail | null> {
  return request<TrackingDetail | null>(`/tracking/${adId}`)
}

export function addTrackingEvent(adId: number, event: TrackingEventInput): Promise<TrackingDetail> {
  return request<TrackingDetail>(`/tracking/${adId}/events`, {
    method: 'POST',
    body: JSON.stringify(event),
  })
}

export function deleteTracking(adId: number): Promise<void> {
  return request<void>(`/tracking/${adId}`, { method: 'DELETE' })
}

export function fetchAssistantStatus(): Promise<AssistantStatus> {
  return request<AssistantStatus>('/assistant')
}

export function interpretWish(
  message: string,
  history: string[],
  previous: AssistantPlan | null,
): Promise<AssistantInterpretResponse> {
  return request<AssistantInterpretResponse>('/assistant/interpret', {
    method: 'POST',
    body: JSON.stringify({ message, history, previous }),
  })
}

export function rankCandidates(message: string, history: string[], plan: AssistantPlan): Promise<AssistantRankResponse> {
  return request<AssistantRankResponse>('/assistant/rank', {
    method: 'POST',
    body: JSON.stringify({ message, history, plan }),
  })
}

export function requestEvaluations(adIds: number[]): Promise<EvaluationRequest[]> {
  return request<EvaluationRequest[]>('/assistant/evaluation-requests', {
    method: 'POST',
    body: JSON.stringify({ ad_ids: adIds }),
  })
}

export function fetchEvaluationRequests(adIds: number[]): Promise<EvaluationRequest[]> {
  const params = new URLSearchParams()
  adIds.forEach((adId) => params.append('ids', String(adId)))
  return request<EvaluationRequest[]>(`/assistant/evaluation-requests?${params}`)
}
