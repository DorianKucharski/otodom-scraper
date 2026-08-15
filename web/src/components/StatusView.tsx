import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { fetchServiceLogs, fetchServices } from '../api/client'
import type { ServiceStatus } from '../api/types'
import { SERVICE_STATUS_LABELS } from '../api/types'

const STATUS_REFRESH_MS = 5000
const LOG_REFRESH_MS = 5000
const LOG_LIMITS = [200, 500, 1000, 2000]
const LEVELS = [
  { value: '', label: 'wszystkie' },
  { value: 'INFO', label: 'INFO i wyżej' },
  { value: 'WARNING', label: 'WARNING i wyżej' },
  { value: 'ERROR', label: 'tylko błędy' },
]

function statusTone(status: string): string {
  if (status === 'running') return 'ok'
  if (status === 'idle' || status === 'starting') return 'waiting'
  if (status === 'stopped') return 'off'
  return 'bad'
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds} s temu`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min temu`
  return `${Math.round(seconds / 3600)} h temu`
}

function formatUptime(startedAt: string | null): string {
  if (!startedAt) return '-'
  const seconds = Math.max(Math.round((Date.now() - new Date(startedAt).getTime()) / 1000), 0)
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h`
  return `${Math.round(seconds / 86400)} dni`
}

function ServiceCard({ service }: { service: ServiceStatus }) {
  const detail = service.detail ?? {}

  return (
    <section className="service-card">
      <header className="service-card-header">
        <span className={`service-lamp service-lamp-${statusTone(service.status)}`} />
        <h3>{service.label}</h3>
        <span className="service-status-text">
          {SERVICE_STATUS_LABELS[service.status] ?? service.status}
        </span>
      </header>

      <dl className="service-attributes">
        <div><dt>Etap</dt><dd>{service.phase ?? '-'}</dd></div>
        <div><dt>Ostatni sygnał</dt><dd>{formatDuration(service.seconds_since_update)}</dd></div>
        <div><dt>Działa od</dt><dd>{formatUptime(service.started_at)}</dd></div>
        {Object.entries(detail).map(([key, value]) => (
          <div key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd>{String(value)}</dd></div>
        ))}
      </dl>

      {service.command && <p className="service-command">{service.command}</p>}

      {!service.is_alive && service.updated_at && (
        <p className="service-warning">
          Proces nie odzywa się od {formatDuration(service.seconds_since_update)}. Kontener jest zatrzymany
          albo zawiesił się w trakcie pracy.
        </p>
      )}
    </section>
  )
}

export function StatusView() {
  const [activeService, setActiveService] = useState<string>('scraper')
  const [limit, setLimit] = useState(500)
  const [minLevel, setMinLevel] = useState('')
  const [search, setSearch] = useState('')
  const [follow, setFollow] = useState(true)
  const logEndRef = useRef<HTMLDivElement>(null)

  const { data: servicesData } = useQuery({
    queryKey: ['services'],
    queryFn: fetchServices,
    refetchInterval: STATUS_REFRESH_MS,
  })

  const { data: logs, isFetching: logsFetching } = useQuery({
    queryKey: ['service-logs', activeService, limit, minLevel, search],
    queryFn: () => fetchServiceLogs(activeService, limit, minLevel || undefined, search || undefined),
    refetchInterval: LOG_REFRESH_MS,
    placeholderData: (previous) => previous,
  })

  useEffect(() => {
    if (follow) logEndRef.current?.scrollIntoView({ block: 'end' })
  }, [logs, follow])

  const services = servicesData ?? []

  return (
    <div className="status-view">
      <div className="service-cards">
        {services.map((service) => <ServiceCard key={service.service} service={service} />)}
        {services.length === 0 && <p className="results-empty">Brak danych o usługach.</p>}
      </div>

      <section className="log-panel">
        <header className="log-toolbar">
          <div className="results-view-switch">
            {services.map((service) => (
              <button
                key={service.service}
                type="button"
                className={activeService === service.service ? 'active' : ''}
                onClick={() => setActiveService(service.service)}
              >
                {service.label}
              </button>
            ))}
          </div>

          <label>
            Poziom
            <select value={minLevel} onChange={(event) => setMinLevel(event.target.value)}>
              {LEVELS.map((level) => (
                <option key={level.value} value={level.value}>{level.label}</option>
              ))}
            </select>
          </label>

          <label>
            Linii
            <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
              {LOG_LIMITS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>

          <label className="log-search">
            Szukaj
            <input
              type="search"
              value={search}
              placeholder="fragment komunikatu"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>

          <label className="filter-checkbox">
            <input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)} />
            <span>Podążaj za końcem</span>
          </label>

          <span className="log-state">{logsFetching ? 'odświeżanie...' : `${logs?.entries.length ?? 0} linii`}</span>
        </header>

        <div className="log-lines">
          {logs?.entries.map((entry) => (
            <div key={entry.id} className={`log-line log-line-${entry.level.toLowerCase()}`}>
              <span className="log-time">{new Date(entry.logged_at).toLocaleTimeString('pl-PL')}</span>
              <span className="log-level">{entry.level}</span>
              <span className="log-logger">{entry.logger_name}</span>
              <span className="log-message">{entry.message}</span>
            </div>
          ))}
          {logs && logs.entries.length === 0 && (
            <p className="results-empty">Brak logów dla tych ustawień.</p>
          )}
          <div ref={logEndRef} />
        </div>
      </section>
    </div>
  )
}
