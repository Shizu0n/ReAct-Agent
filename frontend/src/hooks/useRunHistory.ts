import { useCallback, useEffect, useRef, useState } from 'react'
import type { AgentResponse, RunListItem, RunListResponse } from '../types'

function apiBase(): string {
  const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  return configured ? configured.replace(/\/$/, '') : '/api'
}

export type ListState = 'loading' | 'ready' | 'empty' | 'error'

export type DetailState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ready'; data: AgentResponse }
  | { kind: 'error' }

export function useRunHistory(sessionId: string) {
  const [runs, setRuns] = useState<RunListItem[]>([])
  const [listState, setListState] = useState<ListState>('loading')
  const [selected, setSelected] = useState<string | null>(null)
  const [detailState, setDetailState] = useState<DetailState>({ kind: 'idle' })
  const [reloadToken, setReloadToken] = useState(0)
  const detailRequestRef = useRef(0)

  useEffect(() => {
    let cancelled = false

    async function load(): Promise<void> {
      if (!sessionId) {
        if (!cancelled) {
          setRuns([])
          setListState('empty')
        }
        return
      }

      setListState('loading')
      try {
        const response = await fetch(`${apiBase()}/runs`, {
          headers: { Accept: 'application/json', 'X-Session-Id': sessionId },
        })
        if (!response.ok) throw new Error(String(response.status))
        const payload = (await response.json()) as RunListResponse
        if (cancelled) return
        const list = Array.isArray(payload.runs) ? payload.runs : []
        setRuns(list)
        setListState(list.length > 0 ? 'ready' : 'empty')
      } catch {
        if (cancelled) return
        setRuns([])
        setListState('error')
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [sessionId, reloadToken])

  const refresh = useCallback(() => {
    setReloadToken((token) => token + 1)
  }, [])

  const selectRun = useCallback(
    (runId: string): void => {
      setSelected(runId)
      const token = ++detailRequestRef.current

      if (!sessionId) {
        setDetailState({ kind: 'error' })
        return
      }

      setDetailState({ kind: 'loading' })

      async function load(): Promise<void> {
        try {
          const response = await fetch(`${apiBase()}/trace/${runId}`, {
            headers: { Accept: 'application/json', 'X-Session-Id': sessionId },
          })
          if (!response.ok) throw new Error(String(response.status))
          const data = (await response.json()) as AgentResponse
          if (detailRequestRef.current === token) {
            setDetailState({ kind: 'ready', data })
          }
        } catch {
          if (detailRequestRef.current === token) {
            setDetailState({ kind: 'error' })
          }
        }
      }

      void load()
    },
    [sessionId],
  )

  return { runs, listState, selected, detailState, selectRun, refresh }
}
