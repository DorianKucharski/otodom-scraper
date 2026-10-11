export type FeatureMatchMode = 'all' | 'any'
export type SortDirection = 'asc' | 'desc'

export const SCORE_FIELDS = [
  'overall_score',
  'finish_quality_score',
  'freshness_score',
  'move_in_readiness_score',
  'layout_score',
  'natural_light_score',
  'building_condition_score',
  'location_score',
  'value_for_money_score',
  'photo_trust_score',
] as const

export type ScoreField = (typeof SCORE_FIELDS)[number]

export const SCORE_LABELS: Record<ScoreField, string> = {
  overall_score: 'Ocena ogólna',
  finish_quality_score: 'Jakość wykończenia',
  freshness_score: 'Świeżość',
  move_in_readiness_score: 'Gotowość do wprowadzenia',
  layout_score: 'Rozkład',
  natural_light_score: 'Doświetlenie',
  building_condition_score: 'Stan budynku',
  location_score: 'Lokalizacja',
  value_for_money_score: 'Opłacalność',
  photo_trust_score: 'Wiarygodność zdjęć',
}

export const RENOVATION_LABELS: Record<string, string> = {
  none: 'Nic do zrobienia',
  cosmetic: 'Odświeżenie',
  partial: 'Remont częściowy',
  full: 'Remont generalny',
}

export const TRACKING_STATUSES = [
  'shortlisted',
  'to_call',
  'contacted',
  'viewing_scheduled',
  'viewed',
  'favourite',
  'offer_made',
  'chosen',
  'rejected',
  'unavailable',
] as const

export type TrackingStatus = (typeof TRACKING_STATUSES)[number]

export const TRACKING_LABELS: Record<TrackingStatus, string> = {
  shortlisted: 'Do sprawdzenia',
  to_call: 'Do zadzwonienia',
  contacted: 'Po kontakcie',
  viewing_scheduled: 'Umówione oglądanie',
  viewed: 'Obejrzane',
  favourite: 'Faworyt',
  offer_made: 'Negocjacje / oferta',
  chosen: 'Wybrane',
  rejected: 'Odrzucone',
  unavailable: 'Niedostępne',
}

export const TRACKING_HINTS: Record<TrackingStatus, string> = {
  shortlisted: 'Wpadło w oko, trzeba się przyjrzeć',
  to_call: 'Warte kontaktu, o co zapytać?',
  contacted: 'Czekam: oddzwonią, wyślą zdjęcia, nie odebrał',
  viewing_scheduled: 'Jest termin oglądania',
  viewed: 'Po wizycie, pierwsze wrażenia',
  favourite: 'Poważny kandydat po obejrzeniu',
  offer_made: 'Złożona propozycja lub trwają rozmowy',
  chosen: 'Koniec poszukiwań',
  rejected: 'Rezygnuję, dlaczego?',
  unavailable: 'Sprzedane, wynajęte albo wycofane',
}

export const DISMISSED_TRACKING_STATUSES: TrackingStatus[] = ['rejected', 'unavailable']

export interface Tracking {
  status: TrackingStatus
  viewing_at: string | null
  rating: number | null
  offer_amount: number | null
  price_at_save: number | null
  last_comment: string | null
  created_at: string
  updated_at: string
  updated_by: string | null
}

export interface TrackingEvent {
  id: number
  status: TrackingStatus | null
  comment: string | null
  viewing_at: string | null
  rating: number | null
  offer_amount: number | null
  author: string | null
  created_at: string
}

export interface TrackingDetail extends Tracking {
  ad_id: number
  events: TrackingEvent[]
}

export interface TrackingEventInput {
  status?: TrackingStatus
  comment?: string
  viewing_at?: string
  rating?: number
  offer_amount?: number
}

export interface Session {
  name: string | null
  auth_enabled: boolean
}

export interface AdSearchQuery {
  text?: string
  voivodeships: string[]
  cities: string[]
  districts: string[]
  latitude?: number
  longitude?: number
  radius_m?: number
  min_price?: number
  max_price?: number
  min_price_per_m2?: number
  max_price_per_m2?: number
  max_rent?: number
  min_area?: number
  max_area?: number
  min_rooms?: number
  max_rooms?: number
  min_floor?: number
  max_floor?: number
  exclude_ground_floor: boolean
  exclude_top_floor: boolean
  min_building_year?: number
  max_building_year?: number
  building_types: string[]
  building_materials: string[]
  building_heating: string[]
  markets: string[]
  advertiser_types: string[]
  property_types: string[]
  property_conditions: string[]
  object_types: string[]
  offer_types: string[]
  statuses: string[]
  features: string[]
  feature_match: FeatureMatchMode
  excluded_features: string[]
  min_features_count?: number
  created_after?: string
  modified_after?: string
  require_evaluation: boolean
  renovation_needed: string[]
  style_tags: string[]
  attributes: string[]
  tracking_statuses: TrackingStatus[]
  hide_dismissed: boolean
  sort: string
  direction: SortDirection
  limit: number
  offset: number
  min_overall_score?: number
  min_finish_quality_score?: number
  min_freshness_score?: number
  min_move_in_readiness_score?: number
  min_layout_score?: number
  min_natural_light_score?: number
  min_building_condition_score?: number
  min_location_score?: number
  min_value_for_money_score?: number
  min_photo_trust_score?: number
}

export interface Evaluation {
  status: string
  overall_score: number | null
  finish_quality_score: number | null
  freshness_score: number | null
  move_in_readiness_score: number | null
  layout_score: number | null
  natural_light_score: number | null
  building_condition_score: number | null
  location_score: number | null
  value_for_money_score: number | null
  photo_trust_score: number | null
  renovation_needed: string | null
  style_tag: string | null
  summary: string | null
  strengths: string[]
  concerns: string[]
  attributes: Record<string, string>
  images_evaluated: number
  model: string | null
  evaluated_at: string | null
}

export interface AdSummary {
  id: number
  url: string
  title: string
  price_value: number
  price_currency: string
  price_per_m2: number | null
  rent_value: number | null
  area_value: number | null
  rooms: number | null
  floor: string | null
  building_year: number | null
  offer_type: 'SALE' | 'RENT'
  object_type: 'APARTMENT' | 'HOUSE' | null
  market: string | null
  advertiser_type: string | null
  property_condition: string | null
  city: string | null
  district: string | null
  street: string | null
  latitude: number | null
  longitude: number | null
  distance_m: number | null
  features_count: number
  created_at: string
  modified_at: string
  thumbnail: string | null
  evaluation: Evaluation | null
  tracking: Tracking | null
}

export interface AdImage {
  position: number
  thumbnail: string
  medium: string
  large: string
}

export interface MarketStats {
  ad_count: number
  median_price_per_m2: number | null
  p25_price_per_m2: number | null
  p75_price_per_m2: number | null
  is_city_level: boolean
}

export interface AdDetail extends AdSummary {
  description: string | null
  province: string | null
  county: string | null
  postal_code: string | null
  building_type: string | null
  building_material: string | null
  building_heating: string | null
  building_number_of_floors: number | null
  property_ownership: string | null
  status: string
  images: AdImage[]
  feature_groups: Record<string, string[]>
  screening_attributes: Record<string, string>
  market_stats: MarketStats | null
}

export interface AdSearchResponse {
  total: number
  limit: number
  offset: number
  items: AdSummary[]
}

export interface FacetValue {
  value: string
  label: string
  count: number
  description?: string | null
}

export interface RangeFacet {
  min: number | null
  max: number | null
}

export interface Facets {
  offer_types: FacetValue[]
  object_types: FacetValue[]
  voivodeships: FacetValue[]
  cities: FacetValue[]
  districts: FacetValue[]
  features: FacetValue[]
  building_types: FacetValue[]
  building_materials: FacetValue[]
  building_heating: FacetValue[]
  markets: FacetValue[]
  advertiser_types: FacetValue[]
  property_conditions: FacetValue[]
  style_tags: FacetValue[]
  renovation_needed: FacetValue[]
  price: RangeFacet
  price_per_m2: RangeFacet
  area: RangeFacet
  rooms: RangeFacet
  building_year: RangeFacet
}

export interface SavedSearch {
  id: number
  name: string
  query: Partial<AdSearchQuery>
  created_at: string
  updated_at: string
}

export interface DistrictStats {
  city: string | null
  district: string | null
  ad_count: number
  median_price_per_m2: number | null
  p25_price_per_m2: number | null
  p75_price_per_m2: number | null
  median_price: number | null
  median_area: number | null
  median_overall_score: number | null
}

export interface ServiceStatus {
  service: string
  label: string
  status: string
  reported_status: string | null
  phase: string | null
  detail: Record<string, unknown> | null
  command: string | null
  started_at: string | null
  updated_at: string | null
  seconds_since_update: number | null
  is_alive: boolean
}

export interface ServiceLogEntry {
  id: number
  level: string
  logger_name: string
  message: string
  logged_at: string
}

export interface ServiceLogs {
  service: string
  entries: ServiceLogEntry[]
}

export const SERVICE_STATUS_LABELS: Record<string, string> = {
  starting: 'Uruchamianie',
  running: 'Pracuje',
  idle: 'Czeka',
  failed: 'Błąd',
  stopped: 'Zatrzymany',
  stale: 'Brak sygnału',
  unknown: 'Nigdy nie startował',
}
