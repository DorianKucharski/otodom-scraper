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
  min_days_on_market?: number
  max_days_on_market?: number
  min_listings_count?: number
  price_trends: string[]
  max_price_vs_comparables_pct?: number
  min_price_vs_comparables_pct?: number
  max_price_vs_transactions_pct?: number
  excluded_location_flags: string[]
  hide_unchecked: boolean
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
  object_type: 'APARTMENT' | 'HOUSE' | 'INVESTMENT' | null
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
  last_checked_at: string | null
  thumbnail: string | null
  evaluation: Evaluation | null
  tracking: Tracking | null
  market_signals: MarketSignals | null
}

export interface MarketSignals {
  listing_group_id: number
  listings_count: number
  advertisers_count: number
  first_listed_at: string
  days_on_market: number
  first_price: number | null
  lowest_price: number | null
  highest_price: number | null
  price_change_pct: number | null
  comparables_count: number
  comparables_radius_m: number | null
  comparables_median_price_per_m2: number | null
  comparables_p25_price_per_m2: number | null
  comparables_p75_price_per_m2: number | null
  price_vs_comparables_pct: number | null
  transactions_count: number
  transactions_radius_m: number | null
  transactions_median_price_per_m2: number | null
  transactions_p25_price_per_m2: number | null
  transactions_p75_price_per_m2: number | null
  price_vs_transactions_pct: number | null
  pin_city_name: string | null
  pin_gmina_name: string | null
  city_border_distance_m: number | null
  location_flags: string[]
  location_notes: string[]
  computed_at: string
}

export interface ListingHistoryEntry {
  id: number
  url: string
  title: string
  status: string
  advertiser_type: string | null
  advertiser_name: string | null
  created_at: string
  last_seen_at: string | null
  price_value: number
  area_value: number | null
  city: string | null
  district: string | null
  street: string | null
}

export interface PriceObservation {
  ad_id: number
  observed_at: string
  price_value: number
  status: string | null
}

export interface ListingHistory {
  ad_id: number
  signals: MarketSignals | null
  listings: ListingHistoryEntry[]
  prices: PriceObservation[]
}

export const LOCATION_FLAG_LABELS: Record<string, string> = {
  pin_outside_city: 'Pinezka poza podanym miastem',
  near_city_border: 'Pinezka przy granicy miasta',
  other_place_in_text: 'Opis wymienia sąsiednią miejscowość',
  border_in_text: 'Opis wspomina granicę albo gminę',
  lineage_city_mismatch: 'Inne ogłoszenia lokalu podają inną miejscowość',
}

export const SUSPICIOUS_LOCATION_FLAGS = [
  'pin_outside_city',
  'other_place_in_text',
  'lineage_city_mismatch',
]

export const PRICE_TREND_LABELS: Record<string, string> = {
  dropped: 'Cena spadła',
  raised: 'Cena wzrosła',
  unchanged: 'Bez zmian',
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

export interface AssistantCriterion {
  text: string
  importance: 'must' | 'nice' | string
}

export interface AssistantPlan {
  query: AdSearchQuery
  keywords: string[]
  criteria: AssistantCriterion[]
  understood: string
  sort: string
  warnings: string[]
}

export interface AssistantInterpretResponse {
  plan: AssistantPlan
  cost_usd: number
}

export interface AssistantRankedAd {
  ad: AdSummary
  fit_score: number
  headline: string
  matches: string[]
  gaps: string[]
  evaluated: boolean
}

export interface AssistantRankResponse {
  overview: string
  items: AssistantRankedAd[]
  candidates_considered: number
  total_matching: number
  cost_usd: number
}

export interface AssistantStatus {
  enabled: boolean
  reason: string | null
  spent_today_usd: number
  daily_budget_usd: number
}

export type EvaluationRequestStatus = 'pending' | 'done' | 'rejected' | 'failed'

export interface EvaluationRequest {
  ad_id: number
  status: EvaluationRequestStatus
  message: string | null
  requested_at: string
  finished_at: string | null
}
