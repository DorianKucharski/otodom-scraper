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
}

export interface RangeFacet {
  min: number | null
  max: number | null
}

export interface Facets {
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
