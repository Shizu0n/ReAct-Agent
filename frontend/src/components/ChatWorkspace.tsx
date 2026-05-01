import { useEffect, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import { Activity, Info, PanelRightClose, PanelRightOpen, Route } from 'lucide-react'
import { ChatPanel } from './demo/ChatPanel'
import { ReasoningPanel } from './demo/ReasoningPanel'
import type { AgentState } from '../types'

const loadingLabels = ['Reasoning...', 'Executing tool...', 'Processing observation...']
const RIGHT_SIDEBAR_MIN = 320
const RIGHT_SIDEBAR_MAX = 560

type ChatWorkspaceProps = {
  state: AgentState
  sendQuery: (query: string) => void
  clearHistory: () => void
  sidebarHidden: boolean
  traceOpen: boolean
  rightSidebarWidth: number
  mobileTraceOpen: boolean
  onTraceOpenChange: (open: boolean | ((current: boolean) => boolean)) => void
  onRightSidebarWidthChange: (width: number) => void
  onMobileTraceOpenChange: (open: boolean) => void
  onReasoningStart: () => void
  onOpenPortfolio: () => void
}

export function ChatWorkspace({
  state,
  sendQuery,
  clearHistory,
  sidebarHidden,
  traceOpen,
  rightSidebarWidth,
  mobileTraceOpen,
  onTraceOpenChange,
  onRightSidebarWidthChange,
  onMobileTraceOpenChange,
  onReasoningStart,
  onOpenPortfolio,
}: ChatWorkspaceProps) {
  const [query, setQuery] = useState('')
  const [loadingIndex, setLoadingIndex] = useState(0)

  useEffect(() => {
    if (!state.isLoading) return undefined
    const interval = window.setInterval(() => {
      setLoadingIndex((current) => (current + 1) % loadingLabels.length)
    }, 1500)
    return () => window.clearInterval(interval)
  }, [state.isLoading])

  function submitQuery(value: string): void {
    const trimmed = value.trim()
    if (!trimmed || state.isLoading) return
    onReasoningStart()
    sendQuery(trimmed)
    setQuery('')
  }

  function toggleReasoningTrace(): void {
    if (window.matchMedia('(min-width: 1280px)').matches) {
      onTraceOpenChange((current) => !current)
      return
    }
    onMobileTraceOpenChange(true)
  }

  function startRightResize(event: ReactPointerEvent<HTMLDivElement>): void {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = rightSidebarWidth

    function handlePointerMove(moveEvent: PointerEvent): void {
      const nextWidth = startWidth - (moveEvent.clientX - startX)
      onRightSidebarWidthChange(Math.min(RIGHT_SIDEBAR_MAX, Math.max(RIGHT_SIDEBAR_MIN, nextWidth)))
    }

    function stopResize(): void {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResize)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResize)
  }

  const shouldSignalTrace = state.isLoading && !traceOpen && !mobileTraceOpen

  return (
    <div className="flex h-dvh min-h-screen min-w-0 overflow-x-hidden bg-[var(--bg-primary)]">
      <button
        type="button"
        onClick={toggleReasoningTrace}
        className={`fixed right-4 top-4 z-50 flex h-11 w-11 items-center justify-center overflow-visible rounded-lg border bg-[var(--bg-secondary)] shadow-lg transition-[right,background-color,color,border-color,box-shadow] duration-300 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] ${
          shouldSignalTrace
            ? 'border-[var(--accent-border)] text-[var(--accent-text)] shadow-[0_0_28px_rgba(214,255,127,0.1)]'
            : 'border-[var(--border-default)] text-[var(--text-secondary)]'
        } ${
          traceOpen ? 'xl:right-[calc(var(--right-sidebar-width)+1rem)]' : ''
        }`}
        style={{ '--right-sidebar-width': `${rightSidebarWidth}px` } as CSSProperties}
        aria-label={traceOpen ? 'Hide reasoning trace' : 'Show reasoning trace'}
      >
        {shouldSignalTrace ? (
          <span aria-hidden="true" className="pointer-events-none absolute -right-1 -top-1 flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent-text)] opacity-45" />
            <span className="relative inline-flex h-3 w-3 rounded-full border border-[var(--bg-primary)] bg-[var(--accent-text)]" />
          </span>
        ) : null}
        <span className="hidden xl:block">
          {traceOpen ? <PanelRightClose className="h-5 w-5" /> : <PanelRightOpen className="h-5 w-5" />}
        </span>
        <span className="xl:hidden">
          <Route className="h-5 w-5" />
        </span>
        <span className="absolute -right-1 -top-1 rounded-full border border-[var(--border-default)] bg-[var(--bg-tertiary)] px-1.5 py-0.5 font-mono text-[0.55rem] xl:hidden">
          {state.steps.length}
        </span>
      </button>

      <section className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <header
          className={`flex min-h-[72px] items-center justify-between gap-3 border-b border-[var(--border-subtle)] bg-[var(--bg-primary)] px-4 pl-16 pr-16 xl:pr-20 ${
            sidebarHidden ? 'lg:pl-24' : 'lg:pl-6'
          }`}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
              <span className="relative flex h-2 w-2">
                {state.isLoading ? <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent-text)] opacity-60" /> : null}
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--accent-text)]" />
              </span>
              {state.isLoading ? 'Reasoning live' : 'Agent workspace'}
            </div>
            <h1 className="mt-1 truncate text-base font-semibold text-[var(--text-primary)] sm:text-lg">
              ReAct chat
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onOpenPortfolio}
              className="hidden min-h-11 items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-secondary)] transition hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] sm:inline-flex"
            >
              <Info className="h-4 w-4" />
              About
            </button>
          </div>
        </header>

        {state.error ? (
          <div className="border-b border-[var(--error)]/30 bg-[var(--error-dim)] px-4 py-3 text-sm text-red-200 lg:px-8">
            <span className="inline-flex items-center gap-2 font-mono text-[0.65rem] uppercase tracking-[0.12em]">
              <Activity className="h-3.5 w-3.5" />
              API Error
            </span>
            <span className="ml-3 text-[var(--text-secondary)]">{state.error}</span>
          </div>
        ) : null}

        <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden">
          <ChatPanel
            query={query}
            setQuery={setQuery}
            state={state}
            loadingLabel={loadingLabels[loadingIndex]}
            onSubmit={submitQuery}
            onClearHistory={clearHistory}
          />
        </div>
      </section>

      <ReasoningPanel
        state={state}
        open={traceOpen}
        width={rightSidebarWidth}
        mobileOpen={mobileTraceOpen}
        onOpenChange={onTraceOpenChange}
        onStartResize={startRightResize}
        onMobileOpenChange={onMobileTraceOpenChange}
      />
    </div>
  )
}
