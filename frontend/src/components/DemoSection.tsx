import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import type { AgentState, Message, Step, StepType } from '../types'

const suggestions = [
  'What is the latest Python version?',
  'Calculate √1764 and explain the steps',
  'Search for LangGraph and summarize what it is',
]

const loadingLabels = ['Reasoning...', 'Executing tool...', 'Processing observation...']

type DemoSectionProps = {
  state: AgentState
  sendQuery: (query: string) => void
}

export function DemoSection({ state, sendQuery }: DemoSectionProps) {
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
    sendQuery(trimmed)
    setQuery('')
  }

  return (
    <section id="demo" className="bg-black py-[10vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <SectionHeader
          kicker="Live Demo"
          title="Ask the agent"
          body="Type any research question. Watch the agent reason through it step by step. No backend? The demo runs in mock mode automatically."
        />

        <div className="mt-12 grid gap-5 lg:grid-cols-[3fr_2fr]">
          <ChatPanel
            query={query}
            setQuery={setQuery}
            state={state}
            loadingLabel={loadingLabels[loadingIndex]}
            onSubmit={submitQuery}
          />
          <TracePanel state={state} />
        </div>
      </div>
    </section>
  )
}

function SectionHeader({ kicker, title, body }: { kicker: string; title: string; body: string }) {
  return (
    <div>
      <p className="font-mono text-[0.72rem] uppercase tracking-[0.16em] text-[#6d6d6d]">
        {kicker}
      </p>
      <h2 className="mt-4 max-w-[12ch] text-[clamp(2.7rem,6vw,5.5rem)] font-semibold leading-[0.95] tracking-normal">
        {title}
      </h2>
      <p className="mt-5 max-w-[40rem] text-[#9d9d9d] leading-[1.75]">{body}</p>
    </div>
  )
}

function ChatPanel({
  query,
  setQuery,
  state,
  loadingLabel,
  onSubmit,
}: {
  query: string
  setQuery: (query: string) => void
  state: AgentState
  loadingLabel: string
  onSubmit: (query: string) => void
}) {
  return (
    <div className="flex min-h-[560px] flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#040404]">
      <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4">
        <div className="flex items-center gap-2">
          <motion.span
            className="h-2 w-2 rounded-full bg-[var(--accent)]"
            animate={state.isLoading ? { opacity: [1, 0.3, 1] } : undefined}
            transition={{ repeat: Infinity, duration: 1 }}
          />
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[#6d6d6d]">
            Agent Online
          </span>
        </div>
        <span className="font-mono text-[0.65rem] text-[#555]">GPT-4o-mini · LangGraph</span>
      </div>

      <div className="flex max-h-[420px] min-h-[320px] flex-1 flex-col gap-4 overflow-y-auto p-5">
        {state.messages.length === 0 ? <EmptyChat onSubmit={onSubmit} /> : null}
        {state.messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {state.isLoading ? <LoadingBubble label={loadingLabel} /> : null}
      </div>

      <div className="flex items-end gap-3 border-t border-white/[0.08] p-4">
        <textarea
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSubmit(query)
            }
          }}
          disabled={state.isLoading}
          placeholder="Message the ReAct agent..."
          className="max-h-[100px] flex-1 resize-none rounded-[0.95rem] border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-[0.9rem] leading-[1.4] text-white outline-none placeholder:text-[#777] focus:border-[var(--accent-border)] focus:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="button"
          disabled={state.isLoading || query.trim().length === 0}
          onClick={() => onSubmit(query)}
          className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-full bg-gradient-to-b from-[#f5f5f5] to-[#d9d9d9] text-black transition disabled:cursor-not-allowed disabled:bg-none disabled:bg-[#333] disabled:text-[#777]"
          aria-label="Send query"
        >
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function EmptyChat({ onSubmit }: { onSubmit: (query: string) => void }) {
  return (
    <div className="m-auto flex flex-col gap-3">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          type="button"
          onClick={() => onSubmit(suggestion)}
          className="cursor-pointer rounded-full border border-white/[0.12] bg-white/[0.04] px-4 py-2 font-mono text-[0.65rem] text-[#9d9d9d] transition-colors hover:bg-white/[0.08] hover:text-white"
        >
          {suggestion}
        </button>
      ))}
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  if (!message.content) return null

  const isUser = message.role === 'user'
  return (
    <div className={isUser ? 'self-end text-right' : 'self-start text-left'}>
      <p className="mb-1 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[#6e6e6e]">
        {isUser ? 'You' : 'Agent'}
      </p>
      <div className="max-w-[85%] rounded-2xl border border-white/[0.08] bg-white/[0.06] px-4 py-3 text-[0.9rem] leading-[1.65] text-[#efefef]">
        {message.content}
      </div>
    </div>
  )
}

function LoadingBubble({ label }: { label: string }) {
  return (
    <div className="self-start rounded-2xl border border-white/[0.08] bg-white/[0.06] px-4 py-3 text-[0.9rem] text-[#efefef]">
      <span className="flex items-center gap-2">
        <motion.svg
          className="h-3.5 w-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
        >
          <circle cx="12" cy="12" r="9" opacity="0.25" />
          <path d="M21 12a9 9 0 0 0-9-9" />
        </motion.svg>
        {label}
      </span>
    </div>
  )
}

function TracePanel({ state }: { state: AgentState }) {
  return (
    <div className="flex min-h-[560px] flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#040404]">
      <div className="border-b border-white/[0.08] px-5 py-4 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[#6d6d6d]">
        Reasoning Trace
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto p-4">
        {state.steps.length === 0 && !state.isLoading ? (
          <div className="m-auto whitespace-pre-line text-center font-mono text-[0.8rem] leading-[1.6] text-[#555]">
            {'Run a query to see\nthe agent reasoning'}
          </div>
        ) : (
          <div className="relative flex flex-col gap-1">
            <div className="absolute bottom-0 left-[19px] top-0 w-px bg-white/[0.06]" />
            {state.steps.map((step) => (
              <TraceStep key={`${step.type}-${step.step}-${step.timestamp}`} step={step} />
            ))}
          </div>
        )}

        {state.error ? <ErrorCard error={state.error} /> : null}
      </div>
    </div>
  )
}

function TraceStep({ step }: { step: Step }) {
  return (
    <motion.div
      className="relative pl-8"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <span className={`absolute left-0 top-3 h-[10px] w-[10px] rounded-full ${dotClass(step.type)}`} />
      <div className="mb-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded-full bg-white/[0.06] px-2 py-0.5 font-mono text-[0.62rem] text-[#555]">
            #{String(step.step).padStart(2, '0')}
          </span>
          <span className={`rounded-full px-2 py-0.5 font-mono text-[0.62rem] ${badgeClass(step.type)}`}>
            {step.type === 'observation' ? 'OBSERVE' : step.type.toUpperCase()}
          </span>
          <span className="ml-auto font-mono text-[0.6rem] text-[#555]">
            {new Date(step.timestamp).toLocaleTimeString([], { hour12: false })}
          </span>
        </div>
        <p className="text-[0.82rem] leading-[1.6] text-[#ccc]">{step.content}</p>
        {step.tool ? (
          <p className="mt-1 font-mono text-[0.68rem] text-[#6d6d6d]">→ {step.tool}</p>
        ) : null}
      </div>
    </motion.div>
  )
}

function ErrorCard({ error }: { error: string }) {
  return (
    <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-red-300">
      <span className="rounded-full border border-red-500/30 px-2 py-0.5 font-mono text-[0.62rem]">
        ERROR
      </span>
      <p className="mt-2 text-[0.82rem] leading-[1.6]">{error}</p>
    </div>
  )
}

function dotClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border border-[var(--accent-border)] bg-[var(--accent-dim)]',
    action: 'border border-amber-500/30 bg-amber-500/10',
    observation: 'border border-emerald-500/30 bg-emerald-500/10',
    final: 'border border-white/20 bg-white/10',
  }
  return classes[type]
}

function badgeClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border border-[var(--accent-border)] text-[var(--accent-text)] bg-[var(--accent-dim)]',
    action: 'border border-amber-500/30 text-amber-300 bg-amber-500/10',
    observation: 'border border-emerald-500/30 text-emerald-300 bg-emerald-500/10',
    final: 'border border-white/20 text-white bg-white/[0.06]',
  }
  return classes[type]
}
