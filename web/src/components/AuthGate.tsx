import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

import { ApiError, UNAUTHORIZED_EVENT, fetchSession, login, logout } from '../api/client'
import type { Session } from '../api/types'

const NAME_STORAGE_KEY = 'otodom.user-name'
const SESSION_KEY = ['session']

const SessionContext = createContext<Session | null>(null)

export function useSession(): Session | null {
  return useContext(SessionContext)
}

function storedName(): string {
  try {
    return window.localStorage.getItem(NAME_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function rememberName(name: string) {
  try {
    window.localStorage.setItem(NAME_STORAGE_KEY, name)
  } catch {
    return
  }
}

export function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const { data: session, error, isLoading } = useQuery({
    queryKey: SESSION_KEY,
    queryFn: fetchSession,
    retry: false,
    staleTime: Infinity,
  })

  useEffect(() => {
    const onUnauthorized = () => queryClient.setQueryData(SESSION_KEY, null)
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [queryClient])

  if (isLoading) return <div className="login-screen"><p>Wczytywanie...</p></div>

  const unauthorized = error instanceof ApiError && error.status === 401
  if (error && !unauthorized) {
    return <div className="login-screen"><p className="login-error">Brak połączenia z API: {error.message}</p></div>
  }

  if (!session?.name) {
    return <LoginView passwordRequired={session?.auth_enabled ?? true} />
  }

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}

function LoginView({ passwordRequired }: { passwordRequired: boolean }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(storedName)
  const [password, setPassword] = useState('')

  const submit = useMutation({
    mutationFn: () => login(name.trim(), password),
    onSuccess: (session) => {
      rememberName(session.name ?? '')
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== SESSION_KEY[0] })
      queryClient.setQueryData(SESSION_KEY, session)
    },
  })

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (name.trim()) submit.mutate()
  }

  return (
    <div className="login-screen">
      <form className="login-form" onSubmit={onSubmit}>
        <h1>Mieszkania</h1>
        <label className="filter-field">
          <span>Kto</span>
          <input
            name="username"
            autoComplete="username"
            value={name}
            placeholder="np. Dorian"
            onChange={(event) => setName(event.target.value)}
            maxLength={50}
            autoFocus={!name}
          />
        </label>
        {passwordRequired && (
          <label className="filter-field">
            <span>Hasło</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoFocus={Boolean(name)}
            />
          </label>
        )}
        {submit.error && (
          <p className="login-error">
            {submit.error instanceof ApiError ? submit.error.detail : String(submit.error)}
          </p>
        )}
        <button type="submit" className="primary" disabled={!name.trim() || submit.isPending}>
          {submit.isPending ? 'Loguję...' : 'Zaloguj'}
        </button>
        <p className="login-hint">Logujesz się raz na tym urządzeniu, na rok.</p>
      </form>
    </div>
  )
}

export function SessionBadge() {
  const session = useSession()
  const queryClient = useQueryClient()
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear()
      queryClient.setQueryData(SESSION_KEY, null)
    },
  })

  if (!session?.name) return null

  return (
    <span className="session-badge">
      {session.name}
      <button type="button" onClick={() => signOut.mutate()} title="Wyloguj">Wyloguj</button>
    </span>
  )
}
