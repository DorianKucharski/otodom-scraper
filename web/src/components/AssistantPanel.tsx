import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  DEFAULT_QUERY,
  fetchAssistantStatus,
  fetchEvaluationRequests,
  interpretWish,
  rankCandidates,
  requestEvaluations,
} from '../api/client'
import type { AdSearchQuery, AssistantPlan, AssistantRankResponse, EvaluationRequest } from '../api/types'
import { AdCard } from './AdCard'

interface AssistantPanelProps {
  hidden: boolean
  query: AdSearchQuery
  onApplyQuery: (query: AdSearchQuery) => void
  selectedAdId: number | null
  onSelect: (adId: number) => void
}

type Phase = 'idle' | 'interpreting' | 'ranking'

const POLL_MS = 8000

const REQUEST_LABELS: Record<EvaluationRequest['status'], string> = {
  pending: 'ocena ze zdjęć w kolejce',
  done: 'ocenione ze zdjęć',
  rejected: 'odrzucone w przesiewie',
  failed: 'nie udało się ocenić',
}

function withoutNulls(query: AdSearchQuery): Partial<AdSearchQuery> {
  return Object.fromEntries(Object.entries(query).filter(([, value]) => value !== null)) as Partial<AdSearchQuery>
}

function formatUsd(value: number): string {
  return `${value.toFixed(value < 0.1 ? 3 : 2)} USD`
}

function errorText(error: unknown): string {
  return error instanceof Error && 'detail' in error ? String((error as { detail: string }).detail) : String(error)
}

export function AssistantPanel({ hidden, query, onApplyQuery, selectedAdId, onSelect }: AssistantPanelProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [plan, setPlan] = useState<AssistantPlan | null>(null)
  const [ranking, setRanking] = useState<AssistantRankResponse | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [sessionCost, setSessionCost] = useState(0)
  const [collapsed, setCollapsed] = useState(false)
  const [requestedIds, setRequestedIds] = useState<number[]>([])

  const { data: status } = useQuery({ queryKey: ['assistant-status'], queryFn: fetchAssistantStatus, staleTime: 60_000 })
  const { data: requests } = useQuery({
    queryKey: ['evaluation-requests', requestedIds.join(',')],
    queryFn: () => fetchEvaluationRequests(requestedIds),
    enabled: requestedIds.length > 0,
    refetchInterval: (current) =>
      (current.state.data?.some((item) => item.status === 'pending') ?? true) ? POLL_MS : false,
  })

  const requestById = new Map((requests ?? []).map((item) => [item.ad_id, item]))
  const pendingCount = (requests ?? []).filter((item) => item.status === 'pending').length
  const finishedSinceRanking = requestedIds.length > 0 && pendingCount === 0 && (requests?.length ?? 0) > 0
  const lastMessage = history[history.length - 1]
  const busy = phase !== 'idle'

  const currentPlan = (): AssistantPlan | null => (plan ? { ...plan, query } : null)

  const rank = async (message: string, earlier: string[], rankedPlan: AssistantPlan) => {
    setPhase('ranking')
    const result = await rankCandidates(message, earlier, rankedPlan)
    setRanking(result)
    setSessionCost((cost) => cost + result.cost_usd)
    setCollapsed(false)
  }

  const run = async (action: () => Promise<void>) => {
    setError(null)
    try {
      await action()
    } catch (failure) {
      setError(errorText(failure))
    } finally {
      setPhase('idle')
      queryClient.invalidateQueries({ queryKey: ['assistant-status'] })
    }
  }

  const ask = () => {
    const message = draft.trim()
    if (!message || busy) return
    const earlier = history
    run(async () => {
      setPhase('interpreting')
      const interpreted = await interpretWish(message, earlier, currentPlan())
      setSessionCost((cost) => cost + interpreted.cost_usd)
      const nextQuery = { ...DEFAULT_QUERY, ...withoutNulls(interpreted.plan.query), limit: query.limit, offset: 0 }
      const nextPlan = { ...interpreted.plan, query: nextQuery }
      setPlan(nextPlan)
      setHistory([...earlier, message])
      setDraft('')
      setRanking(null)
      setRequestedIds([])
      onApplyQuery(nextQuery)
      await rank(message, earlier, nextPlan)
    })
  }

  const rerank = () => {
    const refreshed = currentPlan()
    if (!refreshed || !lastMessage || busy) return
    run(async () => {
      setPlan(refreshed)
      await rank(lastMessage, history.slice(0, -1), refreshed)
      setRequestedIds([])
    })
  }

  const reset = () => {
    setHistory([])
    setPlan(null)
    setRanking(null)
    setRequestedIds([])
    setError(null)
  }

  const unevaluatedIds = (ranking?.items ?? [])
    .filter((item) => !item.evaluated && item.ad.object_type !== 'INVESTMENT')
    .map((item) => item.ad.id)

  const evaluate = () =>
    run(async () => {
      const created = await requestEvaluations(unevaluatedIds)
      setRequestedIds(created.map((item) => item.ad_id))
    })

  if (status && !status.enabled) {
    return (
      <section className="assistant assistant-disabled" hidden={hidden}>
        Asystent AI jest wyłączony: {status.reason}
      </section>
    )
  }

  return (
    <section className="assistant" hidden={hidden}>
      <div className="assistant-ask">
        <textarea
          value={draft}
          rows={history.length > 0 ? 1 : 2}
          placeholder={history.length > 0
            ? 'Popraw wyszukiwanie, np. "taniej", "bez parteru", "a coś na Dębnikach?"'
            : 'Opisz, czego szukasz, np. "jasne 3 pokoje w Krakowie do 950 tys., blisko zieleni, do wprowadzenia"'}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) ask()
          }}
        />
        <div className="assistant-ask-actions">
          <button type="button" className="primary" disabled={busy || !draft.trim()} onClick={ask}>
            {phase === 'interpreting' ? 'Rozumiem...' : phase === 'ranking' ? 'Przeglądam...' : 'Zapytaj asystenta'}
          </button>
          {history.length > 0 && <button type="button" disabled={busy} onClick={reset}>Nowa rozmowa</button>}
        </div>
      </div>

      {status && (
        <p className="assistant-meta">
          Ta rozmowa: {formatUsd(sessionCost)} · dziś {formatUsd(status.spent_today_usd)} z {formatUsd(status.daily_budget_usd)}
        </p>
      )}

      {error && <p className="results-error">{error}</p>}

      {history.length > 0 && (
        <ol className="assistant-history">
          {history.map((message, index) => <li key={index}>{message}</li>)}
        </ol>
      )}

      {plan && (
        <div className="assistant-plan">
          {plan.understood && <p>{plan.understood}</p>}
          {plan.warnings.map((warning) => <p key={warning} className="assistant-warning">{warning}</p>)}
          {plan.criteria.length > 0 && (
            <ul className="assistant-criteria">
              {plan.criteria.map((criterion) => (
                <li key={criterion.text} className={`assistant-criterion-${criterion.importance}`}>
                  {criterion.importance === 'must' ? 'musi: ' : 'mile widziane: '}{criterion.text}
                </li>
              ))}
            </ul>
          )}
          {plan.keywords.length > 0 && (
            <p className="assistant-keywords">Szukam w opisach: {plan.keywords.join(', ')}</p>
          )}
          <p className="assistant-hint">
            Filtry po lewej ustawił asystent. Możesz je zmienić i przeliczyć ranking.
          </p>
        </div>
      )}

      {phase === 'ranking' && (
        <p className="assistant-progress">Czytam pasujące ogłoszenia i wybieram najlepsze. To trwa zwykle 15-40 sekund.</p>
      )}

      {ranking && (
        <div className="assistant-ranking">
          <header className="assistant-ranking-header">
            <strong>
              Top {ranking.items.length} z {ranking.candidates_considered} przejrzanych
              ({ranking.total_matching.toLocaleString('pl-PL')} pasuje do filtrów)
            </strong>
            <div className="assistant-ranking-actions">
              {unevaluatedIds.length > 0 && requestedIds.length === 0 && (
                <button type="button" disabled={busy} onClick={evaluate}
                  title="Ocena ze zdjęć kosztuje około 0,04 USD za ogłoszenie i zostaje zapisana w bazie.">
                  Oceń ze zdjęć ({unevaluatedIds.length})
                </button>
              )}
              {requestedIds.length > 0 && pendingCount > 0 && (
                <span className="assistant-pending">Oceniam ze zdjęć: zostało {pendingCount}</span>
              )}
              <button type="button" className={finishedSinceRanking ? 'primary' : ''} disabled={busy} onClick={rerank}>
                {finishedSinceRanking ? 'Przelicz z nowymi ocenami' : 'Przelicz ranking'}
              </button>
              <button type="button" onClick={() => setCollapsed(!collapsed)}>{collapsed ? 'Pokaż' : 'Zwiń'}</button>
            </div>
          </header>

          {!collapsed && (
            <>
              {ranking.overview && <p className="assistant-overview">{ranking.overview}</p>}
              <div className="assistant-results">
                {ranking.items.map((item) => {
                  const requestState = requestById.get(item.ad.id)
                  return (
                    <div key={item.ad.id} className="assistant-result">
                      <div className="assistant-fit">
                        <span className={`assistant-fit-score assistant-fit-${item.fit_score >= 8 ? 'high' : item.fit_score >= 6 ? 'mid' : 'low'}`}>
                          {item.fit_score}/10
                        </span>
                        <p className="assistant-headline">{item.headline}</p>
                        {item.matches.length > 0 && (
                          <ul className="assistant-matches">
                            {item.matches.map((text) => <li key={text}>{text}</li>)}
                          </ul>
                        )}
                        {item.gaps.length > 0 && (
                          <ul className="assistant-gaps">
                            {item.gaps.map((text) => <li key={text}>{text}</li>)}
                          </ul>
                        )}
                        {requestState && (
                          <p className={`assistant-request assistant-request-${requestState.status}`}>
                            {REQUEST_LABELS[requestState.status]}
                            {requestState.message ? `: ${requestState.message}` : ''}
                          </p>
                        )}
                        {!item.evaluated && !requestState && <p className="assistant-request">bez oceny ze zdjęć</p>}
                      </div>
                      <AdCard ad={item.ad} selected={item.ad.id === selectedAdId} onSelect={onSelect} />
                    </div>
                  )
                })}
              </div>
              {ranking.items.length > 0 && <h3 className="assistant-rest">Wszystkie ogłoszenia pasujące do filtrów</h3>}
            </>
          )}
        </div>
      )}
    </section>
  )
}
