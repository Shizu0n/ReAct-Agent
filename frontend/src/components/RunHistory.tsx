import { useState } from 'react'
import { Clock, LoaderCircle, MessageSquare, RotateCw, Search, Terminal, Timer, Wrench } from 'lucide-react'
import { useRunHistory } from '../hooks/useRunHistory'
import type { AgentResponse, ConversationEntry, RunListItem, Step } from '../types'

type RunHistoryProps = {
  sessionId: string
  onOpenInChat?: (entries: ConversationEntry[], threadId: string) => void
}

type ConversationGroup = {
  threadId: string
  runs: RunListItem[]
}

// Runs arrive newest-first, so Map insertion order keeps groups newest-first.
function groupByThread(runs: RunListItem[]): ConversationGroup[] {
  const groups = new Map<string, RunListItem[]>()
  for (const run of runs) {
    const key = run.thread_id || 'legacy'
    const list = groups.get(key)
    if (list) {
      list.push(run)
    } else {
      groups.set(key, [run])
    }
  }
  return [...groups.entries()].map(([threadId, threadRuns]) => ({ threadId, runs: threadRuns }))
}

export function RunHistory({ sessionId, onOpenInChat }: RunHistoryProps) {
  const { runs, listState, selected, detailState, selectRun, refresh, loadConversation } = useRunHistory(sessionId)
  const [restoringThread, setRestoringThread] = useState<string | null>(null)

  async function handleOpenInChat(threadId: string): Promise<void> {
    if (restoringThread !== null || !onOpenInChat) return
    setRestoringThread(threadId)
    try {
      const entries = await loadConversation(threadId)
      if (entries.length > 0) onOpenInChat(entries, threadId)
    } finally {
      setRestoringThread(null)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1200px] flex-col px-[clamp(1.25rem,4vw,3rem)] py-[8vh]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
            Observable, not opaque
          </p>
          <h2 className="mt-4 text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-[0.95] tracking-tight text-white">
            Run history
          </h2>
          <p className="mt-4 max-w-[620px] text-[0.9rem] leading-[1.7] text-[var(--text-secondary)]">
            Every conversation is persisted with its full reasoning traces, per-step timing, and any
            provider fallbacks. Pick a run to inspect how the agent reached its answer, or reopen a
            conversation back in Chat.
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="mt-1 inline-flex shrink-0 items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-tertiary)] px-3 py-2 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
          aria-label="Refresh run history"
        >
          <RotateCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      <div className="mt-10 grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,380px)_1fr]">
        <div className="min-w-0">
          <RunList
            state={listState}
            runs={runs}
            selected={selected}
            onSelect={selectRun}
            onRetry={refresh}
            restoringThread={restoringThread}
            onOpenInChat={onOpenInChat ? (threadId) => void handleOpenInChat(threadId) : undefined}
          />
        </div>
        <div className="min-w-0">
          <RunDetail selected={selected} state={detailState} />
        </div>
      </div>
    </div>
  )
}

function RunList({
  state,
  runs,
  selected,
  onSelect,
  onRetry,
  restoringThread,
  onOpenInChat,
}: {
  state: ReturnType<typeof useRunHistory>['listState']
  runs: RunListItem[]
  selected: string | null
  onSelect: (runId: string) => void
  onRetry: () => void
  restoringThread: string | null
  onOpenInChat?: (threadId: string) => void
}) {
  if (state === 'loading') {
    return <PanelNote>Loading runs…</PanelNote>
  }

  if (state === 'error') {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--border-default)] bg-[var(--bg-secondary)] p-6">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          History unavailable
        </p>
        <p className="mt-3 text-[0.85rem] leading-[1.6] text-[var(--text-secondary)]">
          Could not reach the run-history service. The backend may be paused or offline.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-tertiary)] px-3 py-2 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
        >
          <RotateCw className="h-3.5 w-3.5" />
          Try again
        </button>
      </div>
    )
  }

  if (state === 'empty') {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--border-default)] bg-[var(--bg-secondary)] p-6">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          No runs yet
        </p>
        <p className="mt-3 text-[0.85rem] leading-[1.6] text-[var(--text-secondary)]">
          Ask the agent something in Chat and it will appear here with its full trace.
        </p>
      </div>
    )
  }

  return (
    <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
      {groupByThread(runs).map((group) => (
        <ConversationCard
          key={group.threadId}
          group={group}
          selected={selected}
          restoring={restoringThread === group.threadId}
          anyRestoring={restoringThread !== null}
          onSelect={onSelect}
          onOpenInChat={onOpenInChat}
        />
      ))}
    </div>
  )
}

function ConversationCard({
  group,
  selected,
  restoring,
  anyRestoring,
  onSelect,
  onOpenInChat,
}: {
  group: ConversationGroup
  selected: string | null
  restoring: boolean
  anyRestoring: boolean
  onSelect: (runId: string) => void
  onOpenInChat?: (threadId: string) => void
}) {
  // Newest-first within the group; the oldest run opened the conversation.
  const firstRun = group.runs[group.runs.length - 1]
  const latestRun = group.runs[0]

  return (
    <section className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)]/60 p-2">
      <div className="flex items-start justify-between gap-3 px-2 pb-2 pt-1.5">
        <div className="min-w-0">
          <p className="truncate text-[0.8rem] font-medium text-[var(--text-primary)]" title={firstRun.query}>
            {firstRun.query || 'Untitled conversation'}
          </p>
          <p className="mt-0.5 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[var(--text-tertiary)]">
            {group.runs.length} run{group.runs.length === 1 ? '' : 's'} · {formatDate(latestRun.created_at)}
          </p>
        </div>
        {onOpenInChat ? (
          <button
            type="button"
            onClick={() => onOpenInChat(group.threadId)}
            disabled={anyRestoring}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--accent-border)] bg-[var(--bg-elevated)] px-2.5 py-1.5 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[var(--accent-text)] transition hover:bg-[var(--bg-tertiary)] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Open this conversation in chat"
          >
            {restoring ? <LoaderCircle className="h-3 w-3 animate-spin" /> : <MessageSquare className="h-3 w-3" />}
            {restoring ? 'Loading…' : 'Open in chat'}
          </button>
        ) : null}
      </div>
      <div className="space-y-2">
        {group.runs.map((run) => (
          <RunRow key={run.run_id} run={run} active={run.run_id === selected} onSelect={onSelect} />
        ))}
      </div>
    </section>
  )
}

function RunRow({
  run,
  active,
  onSelect,
}: {
  run: RunListItem
  active: boolean
  onSelect: (runId: string) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(run.run_id)}
      aria-current={active ? 'true' : undefined}
      className={`w-full rounded-xl border p-4 text-left transition ${
        active
          ? 'border-[var(--accent-border)] bg-[var(--bg-elevated)]'
          : 'border-[var(--border-subtle)] bg-[var(--bg-secondary)] hover:border-[var(--border-default)] hover:bg-[var(--bg-tertiary)]'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
          {formatDate(run.created_at)}
        </span>
        <StatusPill status={run.status} />
      </div>
      <p className="mt-2 truncate text-[0.85rem] text-[var(--text-primary)]" title={run.query}>
        {run.query || 'Untitled run'}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Chip icon={<Clock className="h-3 w-3" />} value={formatElapsed(run.elapsed_ms)} />
        {run.provider ? <Chip icon={<Wrench className="h-3 w-3" />} value={run.provider} /> : null}
        {run.has_fallback ? <FallbackBadge /> : null}
      </div>
    </button>
  )
}

function RunDetail({
  selected,
  state,
}: {
  selected: string | null
  state: ReturnType<typeof useRunHistory>['detailState']
}) {
  if (selected === null || state.kind === 'idle') {
    return (
      <div className="grid min-h-[320px] place-items-center rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-6 text-center">
        <p className="max-w-[280px] font-mono text-[0.72rem] leading-[1.6] text-[var(--text-tertiary)]">
          Select a run to inspect its reasoning trace, timing, and provider fallbacks.
        </p>
      </div>
    )
  }

  if (state.kind === 'loading') {
    return <PanelNote>Loading trace…</PanelNote>
  }

  if (state.kind === 'error') {
    return (
      <div className="rounded-2xl border border-[var(--error)]/30 bg-[var(--error-dim)] p-6 text-red-300">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em]">Trace unavailable</p>
        <p className="mt-3 text-[0.85rem] leading-[1.6]">
          Could not load this run's trace. It may have expired or the backend is unreachable.
        </p>
      </div>
    )
  }

  return <TraceView response={state.data} />
}

function TraceView({ response }: { response: AgentResponse }) {
  const steps = response.steps.length > 0 ? response.steps : response.trace
  const usage = response.usage
  const fallbacks = usage?.fallback_events ?? []
  const winner = usage?.providers?.[0]

  return (
    <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-secondary)] p-5">
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-subtle)] pb-4">
        <StatusPill status={response.status} />
        <Chip icon={<Clock className="h-3 w-3" />} value={formatElapsed(response.latency_ms)} />
        {usage && usage.total_tokens > 0 ? (
          <>
            <Chip value={`${usage.total_tokens.toLocaleString('en-US')} tok (${usage.llm_calls} calls)`} />
            <Chip value={`$${usage.estimated_cost_usd.toFixed(4)}`} />
          </>
        ) : null}
        {usage?.providers?.length ? (
          <Chip icon={<Wrench className="h-3 w-3" />} value={usage.providers.join(' → ')} />
        ) : null}
      </div>

      {fallbacks.length > 0 ? (
        <div className="mt-4 rounded-xl border border-[var(--action-border)] bg-[var(--action-dim)] p-4">
          <p className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-[var(--action)]">
            Provider fallbacks
          </p>
          <ul className="mt-2 space-y-1">
            {fallbacks.map((event, index) => (
              <li key={`${event.provider}-${index}`} className="text-[0.8rem] text-[var(--text-secondary)]">
                <span className="text-[var(--text-primary)]">{event.provider}</span> failed →{' '}
                <span className="text-[var(--text-primary)]">{winner ?? 'next provider'}</span>
                {event.error ? (
                  <span className="ml-2 font-mono text-[0.62rem] text-[var(--text-tertiary)]" title={event.error}>
                    {event.error}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-5 space-y-3">
        {steps.length === 0 ? (
          <p className="font-mono text-[0.72rem] text-[var(--text-tertiary)]">
            Answered directly — no tool calls in this run.
          </p>
        ) : (
          steps.map((step, index) => <StepCard key={index} step={step} index={index + 1} />)
        )}
        <FinalCard answer={response.answer || response.result} />
      </div>
    </div>
  )
}

function StepCard({ step, index }: { step: Step; index: number }) {
  const thought = step.thought ?? (step.type === 'thought' ? step.content : undefined)
  const action = step.action ?? (step.type === 'action' ? step.tool : undefined)
  const observation = step.observation ?? (step.type === 'observation' ? step.content : undefined)

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]/45 p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="font-mono text-[0.58rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
          {String(index).padStart(2, '0')}
        </span>
        {typeof step.elapsed_ms === 'number' ? (
          <span className="ml-auto inline-flex items-center gap-1 font-mono text-[0.58rem] text-[var(--text-tertiary)]">
            <Timer className="h-3 w-3" />
            {step.elapsed_ms}ms
          </span>
        ) : null}
      </div>

      {thought ? <SubLine type="thought" icon={<Timer className="h-3 w-3" />} label="Thought" text={thought} /> : null}
      {action ? (
        <SubLine
          type="action"
          icon={<Terminal className="h-3 w-3" />}
          label="Action"
          text={step.action_input ? `${action} · ${step.action_input}` : action}
        />
      ) : null}
      {observation ? (
        <SubLine type="observation" icon={<Search className="h-3 w-3" />} label="Observe" text={observation} />
      ) : null}
    </div>
  )
}

function SubLine({
  type,
  icon,
  label,
  text,
}: {
  type: 'thought' | 'action' | 'observation'
  icon: React.ReactNode
  label: string
  text: string
}) {
  const color = {
    thought: 'text-[var(--thought)]',
    action: 'text-[var(--action)]',
    observation: 'text-[var(--observation)]',
  }[type]

  return (
    <div className="mt-2 first:mt-0">
      <span className={`inline-flex items-center gap-1 font-mono text-[0.58rem] uppercase tracking-[0.12em] ${color}`}>
        {icon}
        {label}
      </span>
      <p className="mt-1 whitespace-pre-line break-words text-[0.8rem] leading-[1.6] text-[var(--text-secondary)]">
        {text}
      </p>
    </div>
  )
}

function FinalCard({ answer }: { answer: string }) {
  if (!answer) return null
  return (
    <div className="rounded-xl border border-[var(--border-strong)] bg-white/5 p-4">
      <span className="font-mono text-[0.58rem] uppercase tracking-[0.12em] text-[var(--text-primary)]">
        Final
      </span>
      <p className="mt-1 whitespace-pre-line break-words text-[0.82rem] leading-[1.65] text-[var(--text-primary)]">
        {answer}
      </p>
    </div>
  )
}

function StatusPill({ status }: { status: 'success' | 'error' }) {
  const ok = status === 'success'
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[0.58rem] uppercase tracking-[0.12em] ${
        ok
          ? 'border-[var(--observation-border)] bg-[var(--observation-dim)] text-[var(--observation)]'
          : 'border-[var(--error)]/40 bg-[var(--error-dim)] text-red-300'
      }`}
    >
      {status}
    </span>
  )
}

function FallbackBadge() {
  return (
    <span className="rounded-full border border-[var(--action-border)] bg-[var(--action-dim)] px-2 py-0.5 font-mono text-[0.58rem] uppercase tracking-[0.12em] text-[var(--action)]">
      fallback
    </span>
  )
}

function Chip({ icon, value }: { icon?: React.ReactNode; value: string }) {
  return (
    <span
      className="inline-flex max-w-full items-center gap-1.5 truncate rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]/55 px-2.5 py-1 font-mono text-[0.62rem] text-[var(--text-secondary)]"
      title={value}
    >
      {icon ? <span className="shrink-0 text-[var(--accent-text)]">{icon}</span> : null}
      <span className="truncate">{value}</span>
    </span>
  )
}

function PanelNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-6">
      <p className="font-mono text-[0.8rem] text-[var(--text-tertiary)]">{children}</p>
    </div>
  )
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
