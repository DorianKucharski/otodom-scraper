import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { createSavedSearch, deleteSavedSearch, fetchSavedSearches } from '../api/client'
import type { AdSearchQuery } from '../api/types'

interface SavedSearchesProps {
  query: AdSearchQuery
  onApply: (query: AdSearchQuery) => void
}

export function SavedSearches({ query, onApply }: SavedSearchesProps) {
  const [name, setName] = useState('')
  const queryClient = useQueryClient()
  const { data: savedSearches = [] } = useQuery({ queryKey: ['saved-searches'], queryFn: fetchSavedSearches })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['saved-searches'] })
  const create = useMutation({
    mutationFn: () => createSavedSearch(name.trim(), query),
    onSuccess: () => {
      setName('')
      invalidate()
    },
  })
  const remove = useMutation({ mutationFn: deleteSavedSearch, onSuccess: invalidate })

  return (
    <div className="saved-searches">
      <select
        value=""
        onChange={(event) => {
          const saved = savedSearches.find((item) => String(item.id) === event.target.value)
          if (saved) onApply(saved.query as AdSearchQuery)
        }}
      >
        <option value="">Zapisane wyszukiwania</option>
        {savedSearches.map((saved) => (
          <option key={saved.id} value={saved.id}>{saved.name}</option>
        ))}
      </select>

      <input
        type="text"
        value={name}
        placeholder="Nazwa wyszukiwania"
        onChange={(event) => setName(event.target.value)}
      />
      <button type="button" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
        Zapisz
      </button>

      {savedSearches.length > 0 && (
        <ul className="saved-search-list">
          {savedSearches.map((saved) => (
            <li key={saved.id}>
              <button type="button" onClick={() => onApply(saved.query as AdSearchQuery)}>{saved.name}</button>
              <button type="button" className="saved-search-delete" onClick={() => remove.mutate(saved.id)}>×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
