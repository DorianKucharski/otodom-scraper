import { useState } from 'react'

import type { AdSearchQuery, Facets, FacetValue } from '../api/types'
import { SCORE_FIELDS, SCORE_LABELS, TRACKING_LABELS, TRACKING_STATUSES } from '../api/types'

interface FilterPanelProps {
  query: AdSearchQuery
  facets?: Facets
  onChange: (patch: Partial<AdSearchQuery>) => void
  onReset: () => void
  onClose: () => void
}

interface SectionProps {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}

function Section({ title, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className="filter-section">
      <button type="button" className="filter-section-header" onClick={() => setOpen(!open)}>
        <span>{title}</span>
        <span>{open ? '−' : '+'}</span>
      </button>
      {open && <div className="filter-section-body">{children}</div>}
    </section>
  )
}

interface NumberRangeProps {
  label: string
  unit?: string
  minValue?: number
  maxValue?: number
  onChangeMin: (value?: number) => void
  onChangeMax: (value?: number) => void
}

function NumberRange({ label, unit, minValue, maxValue, onChangeMin, onChangeMax }: NumberRangeProps) {
  return (
    <label className="filter-field">
      <span>{label}{unit ? ` (${unit})` : ''}</span>
      <span className="filter-range">
        <input
          type="number"
          placeholder="od"
          value={minValue ?? ''}
          onChange={(event) => onChangeMin(event.target.value ? Number(event.target.value) : undefined)}
        />
        <input
          type="number"
          placeholder="do"
          value={maxValue ?? ''}
          onChange={(event) => onChangeMax(event.target.value ? Number(event.target.value) : undefined)}
        />
      </span>
    </label>
  )
}

interface MultiSelectProps {
  label: string
  options: FacetValue[]
  selected: string[]
  onChange: (values: string[]) => void
  size?: number
}

const SEARCHABLE_FROM = 12
const MAX_VISIBLE_OPTIONS = 100
const ROW_HEIGHT_PX = 30

function MultiSelect({ label, options, selected, onChange, size = 6 }: MultiSelectProps) {
  const [search, setSearch] = useState('')
  const needle = search.trim().toLowerCase()
  const known = new Set(options.map((option) => option.value))
  const orphans: FacetValue[] = selected
    .filter((value) => !known.has(value))
    .map((value) => ({ value, label: value, count: 0 }))
  const chosen = [...orphans, ...options.filter((option) => selected.includes(option.value))]
  const matching = options.filter(
    (option) => !selected.includes(option.value) && (!needle || option.label.toLowerCase().includes(needle)),
  )
  const visible = [...chosen, ...matching.slice(0, MAX_VISIBLE_OPTIONS)]
  const hidden = matching.length - Math.min(matching.length, MAX_VISIBLE_OPTIONS)
  const hasDescriptions = options.some((option) => option.description)

  const toggle = (value: string, checked: boolean) =>
    onChange(checked ? [...selected, value] : selected.filter((item) => item !== value))

  return (
    <div className="filter-field">
      <span className="filter-multi-header">
        {label}
        {selected.length > 0 && (
          <button type="button" className="filter-multi-clear" onClick={() => onChange([])}>
            wyczyść ({selected.length})
          </button>
        )}
      </span>
      {options.length >= SEARCHABLE_FROM && (
        <input type="search" value={search} placeholder="szukaj..." onChange={(event) => setSearch(event.target.value)} />
      )}
      <div
        className="filter-multi"
        style={hasDescriptions ? undefined : { maxHeight: `${Math.max(size, 3) * ROW_HEIGHT_PX}px` }}
      >
        {visible.map((option) => (
          <label key={option.value} className="filter-multi-option">
            <input
              type="checkbox"
              checked={selected.includes(option.value)}
              onChange={(event) => toggle(option.value, event.target.checked)}
            />
            <span className="filter-multi-text">
              <span className="filter-multi-label">
                {option.label}
                {option.count > 0 && <span className="filter-multi-count">{option.count.toLocaleString('pl-PL')}</span>}
              </span>
              {option.description && <span className="filter-multi-description">{option.description}</span>}
            </span>
          </label>
        ))}
        {visible.length === 0 && <span className="filter-multi-empty">brak</span>}
        {hidden > 0 && (
          <span className="filter-multi-empty">
            i {hidden.toLocaleString('pl-PL')} więcej, wpisz nazwę w wyszukiwarce
          </span>
        )}
      </div>
    </div>
  )
}

interface ChoiceSwitchProps {
  label: string
  options: FacetValue[]
  order: string[]
  selected: string[]
  onChange: (values: string[]) => void
}

function ChoiceSwitch({ label, options, order, selected, onChange }: ChoiceSwitchProps) {
  const sorted = [...options].sort((left, right) => order.indexOf(left.value) - order.indexOf(right.value))
  const choices: Array<{ value: string; label: string; count?: number }> = [{ value: '', label: 'Wszystkie' }, ...sorted]

  return (
    <div className="filter-offer-switch" role="group" aria-label={label}>
      {choices.map((choice) => {
        const active = choice.value === '' ? selected.length === 0 : selected.length === 1 && selected[0] === choice.value
        return (
          <button
            key={choice.value || 'all'}
            type="button"
            className={active ? 'active' : ''}
            onClick={() => onChange(choice.value ? [choice.value] : [])}
          >
            {choice.label}
            {choice.count !== undefined && <span>{choice.count.toLocaleString('pl-PL')}</span>}
          </button>
        )
      })}
    </div>
  )
}

interface ScoreSliderProps {
  label: string
  value?: number
  onChange: (value?: number) => void
}

function ScoreSlider({ label, value, onChange }: ScoreSliderProps) {
  return (
    <label className="filter-field filter-slider">
      <span>
        {label}
        <strong>{value ? `min ${value}` : 'dowolna'}</strong>
      </span>
      <input
        type="range"
        min={0}
        max={10}
        step={1}
        value={value ?? 0}
        onChange={(event) => {
          const next = Number(event.target.value)
          onChange(next === 0 ? undefined : next)
        }}
      />
    </label>
  )
}

export function FilterPanel({ query, facets, onChange, onReset, onClose }: FilterPanelProps) {
  const [attributeDraft, setAttributeDraft] = useState('')


  return (
    <aside className="filter-panel">
      <div className="filter-panel-header">
        <h2>Filtry</h2>
        <button type="button" onClick={onReset}>Wyczyść</button>
        <button type="button" className="mobile-only primary" onClick={onClose}>Pokaż wyniki</button>
      </div>

      <ChoiceSwitch
        label="Typ oferty"
        options={facets?.offer_types ?? []}
        order={['SALE', 'RENT']}
        selected={query.offer_types}
        onChange={(offer_types) => onChange({ offer_types })}
      />
      <ChoiceSwitch
        label="Rodzaj nieruchomości"
        options={facets?.object_types ?? []}
        order={['APARTMENT', 'HOUSE', 'INVESTMENT']}
        selected={query.object_types}
        onChange={(object_types) => onChange({ object_types })}
      />
      {query.offer_types.includes('RENT') && (
        <p className="filter-caption">Przy wynajmie cena to miesięczny czynsz.</p>
      )}

      <label className="filter-field">
        <span>Szukaj w tytule i opisie</span>
        <input
          type="search"
          value={query.text ?? ''}
          placeholder="np. kamienica, ogród, garaż"
          onChange={(event) => onChange({ text: event.target.value || undefined })}
        />
      </label>

      <Section title="Moje statusy">
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={query.hide_dismissed}
            onChange={(event) => onChange({ hide_dismissed: event.target.checked })}
          />
          <span>Ukryj odrzucone i niedostępne</span>
        </label>
        <span className="filter-caption">Tylko ze statusem</span>
        {TRACKING_STATUSES.map((status) => (
          <label key={status} className="filter-checkbox">
            <input
              type="checkbox"
              checked={query.tracking_statuses.includes(status)}
              onChange={(event) => onChange({
                tracking_statuses: event.target.checked
                  ? [...query.tracking_statuses, status]
                  : query.tracking_statuses.filter((item) => item !== status),
              })}
            />
            <span>{TRACKING_LABELS[status]}</span>
          </label>
        ))}
      </Section>

      <Section title="Lokalizacja" defaultOpen>
        <MultiSelect
          label="Województwo"
          options={facets?.voivodeships ?? []}
          selected={query.voivodeships}
          onChange={(voivodeships) => onChange({ voivodeships })}
        />
        <MultiSelect
          label="Miasto"
          options={facets?.cities ?? []}
          selected={query.cities}
          onChange={(cities) => onChange({ cities })}
          size={8}
        />
        <MultiSelect
          label="Dzielnica"
          options={facets?.districts ?? []}
          selected={query.districts}
          onChange={(districts) => onChange({ districts })}
          size={8}
        />
        <div className="filter-radius">
          <label className="filter-field">
            <span>Szerokość</span>
            <input
              type="number"
              step="0.0001"
              value={query.latitude ?? ''}
              onChange={(event) => onChange({ latitude: event.target.value ? Number(event.target.value) : undefined })}
            />
          </label>
          <label className="filter-field">
            <span>Długość</span>
            <input
              type="number"
              step="0.0001"
              value={query.longitude ?? ''}
              onChange={(event) => onChange({ longitude: event.target.value ? Number(event.target.value) : undefined })}
            />
          </label>
          <label className="filter-field">
            <span>Promień (m)</span>
            <input
              type="number"
              step="100"
              value={query.radius_m ?? ''}
              onChange={(event) => onChange({ radius_m: event.target.value ? Number(event.target.value) : undefined })}
            />
          </label>
        </div>
      </Section>

      <Section title="Cena" defaultOpen>
        <NumberRange
          label="Cena"
          unit="zł"
          minValue={query.min_price}
          maxValue={query.max_price}
          onChangeMin={(min_price) => onChange({ min_price })}
          onChangeMax={(max_price) => onChange({ max_price })}
        />
        <NumberRange
          label="Cena za metr"
          unit="zł/m²"
          minValue={query.min_price_per_m2}
          maxValue={query.max_price_per_m2}
          onChangeMin={(min_price_per_m2) => onChange({ min_price_per_m2 })}
          onChangeMax={(max_price_per_m2) => onChange({ max_price_per_m2 })}
        />
        <label className="filter-field">
          <span>Czynsz maksymalny (zł)</span>
          <input
            type="number"
            value={query.max_rent ?? ''}
            onChange={(event) => onChange({ max_rent: event.target.value ? Number(event.target.value) : undefined })}
          />
        </label>
      </Section>

      <Section title="Parametry" defaultOpen>
        <NumberRange
          label="Powierzchnia"
          unit="m²"
          minValue={query.min_area}
          maxValue={query.max_area}
          onChangeMin={(min_area) => onChange({ min_area })}
          onChangeMax={(max_area) => onChange({ max_area })}
        />
        <NumberRange
          label="Liczba pokoi"
          minValue={query.min_rooms}
          maxValue={query.max_rooms}
          onChangeMin={(min_rooms) => onChange({ min_rooms })}
          onChangeMax={(max_rooms) => onChange({ max_rooms })}
        />
        <NumberRange
          label="Piętro"
          minValue={query.min_floor}
          maxValue={query.max_floor}
          onChangeMin={(min_floor) => onChange({ min_floor })}
          onChangeMax={(max_floor) => onChange({ max_floor })}
        />
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={query.exclude_ground_floor}
            onChange={(event) => onChange({ exclude_ground_floor: event.target.checked })}
          />
          <span>Bez parteru</span>
        </label>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={query.exclude_top_floor}
            onChange={(event) => onChange({ exclude_top_floor: event.target.checked })}
          />
          <span>Bez ostatniego piętra</span>
        </label>
        <NumberRange
          label="Rok budowy"
          minValue={query.min_building_year}
          maxValue={query.max_building_year}
          onChangeMin={(min_building_year) => onChange({ min_building_year })}
          onChangeMax={(max_building_year) => onChange({ max_building_year })}
        />
      </Section>

      <Section title="Budynek i oferta">
        <MultiSelect
          label="Typ budynku"
          options={facets?.building_types ?? []}
          selected={query.building_types}
          onChange={(building_types) => onChange({ building_types })}
        />
        <MultiSelect
          label="Materiał"
          options={facets?.building_materials ?? []}
          selected={query.building_materials}
          onChange={(building_materials) => onChange({ building_materials })}
        />
        <MultiSelect
          label="Ogrzewanie"
          options={facets?.building_heating ?? []}
          selected={query.building_heating}
          onChange={(building_heating) => onChange({ building_heating })}
        />
        <MultiSelect
          label="Rynek"
          options={facets?.markets ?? []}
          selected={query.markets}
          onChange={(markets) => onChange({ markets })}
          size={3}
        />
        <MultiSelect
          label="Ogłaszający"
          options={facets?.advertiser_types ?? []}
          selected={query.advertiser_types}
          onChange={(advertiser_types) => onChange({ advertiser_types })}
          size={3}
        />
        <MultiSelect
          label="Stan wg serwisu"
          options={facets?.property_conditions ?? []}
          selected={query.property_conditions}
          onChange={(property_conditions) => onChange({ property_conditions })}
          size={4}
        />
      </Section>

      <Section title="Cechy">
        <label className="filter-field">
          <span>Dopasowanie</span>
          <select
            value={query.feature_match}
            onChange={(event) => onChange({ feature_match: event.target.value as AdSearchQuery['feature_match'] })}
          >
            <option value="all">wszystkie zaznaczone</option>
            <option value="any">dowolna zaznaczona</option>
          </select>
        </label>
        <MultiSelect
          label="Wymagane"
          options={facets?.features ?? []}
          selected={query.features}
          onChange={(features) => onChange({ features })}
          size={10}
        />
        <MultiSelect
          label="Wykluczone"
          options={facets?.features ?? []}
          selected={query.excluded_features}
          onChange={(excluded_features) => onChange({ excluded_features })}
          size={6}
        />
        <label className="filter-field">
          <span>Minimalna liczba cech</span>
          <input
            type="number"
            value={query.min_features_count ?? ''}
            onChange={(event) =>
              onChange({ min_features_count: event.target.value ? Number(event.target.value) : undefined })
            }
          />
        </label>
      </Section>

      <Section title="Oceny AI" defaultOpen>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={query.require_evaluation}
            onChange={(event) => onChange({ require_evaluation: event.target.checked })}
          />
          <span>Tylko ocenione przez AI</span>
        </label>

        {SCORE_FIELDS.map((field) => (
          <ScoreSlider
            key={field}
            label={SCORE_LABELS[field]}
            value={query[`min_${field}` as keyof AdSearchQuery] as number | undefined}
            onChange={(value) => onChange({ [`min_${field}`]: value } as Partial<AdSearchQuery>)}
          />
        ))}

        <MultiSelect
          label="Zakres prac"
          options={facets?.renovation_needed ?? []}
          selected={query.renovation_needed}
          onChange={(renovation_needed) => onChange({ renovation_needed })}
          size={4}
        />
        <MultiSelect
          label="Styl wnętrza"
          options={facets?.style_tags ?? []}
          selected={query.style_tags}
          onChange={(style_tags) => onChange({ style_tags })}
          size={6}
        />

        <label className="filter-field">
          <span>Atrybuty AI (klucz:wartość)</span>
          <span className="filter-range">
            <input
              type="text"
              value={attributeDraft}
              placeholder="kitchen_type:zamknięta"
              onChange={(event) => setAttributeDraft(event.target.value)}
            />
            <button
              type="button"
              onClick={() => {
                if (attributeDraft.includes(':')) {
                  onChange({ attributes: [...query.attributes, attributeDraft] })
                  setAttributeDraft('')
                }
              }}
            >
              Dodaj
            </button>
          </span>
        </label>
        <ul className="filter-chips">
          {query.attributes.map((attribute) => (
            <li key={attribute}>
              {attribute}
              <button
                type="button"
                onClick={() => onChange({ attributes: query.attributes.filter((item) => item !== attribute) })}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </Section>
    </aside>
  )
}
