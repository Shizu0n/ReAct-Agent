import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { ArrowUp, CircuitBoard, Sparkles, Terminal, Wrench } from 'lucide-react'
import clsx from 'clsx'
import type { AgentState, Message } from '../../types'
import { MessageMarkdown } from './MessageMarkdown'

const suggestions = [
  'What is the latest Python version?',
  'Calculate sqrt(1764) and explain the steps',
  'Search for LangGraph and summarize what it is',
]

type ChatPanelProps = {
  query: string
  setQuery: (query: string) => void
  state: AgentState
  loadingLabel: string
  onSubmit: (query: string) => void
}

export function ChatPanel({ query, setQuery, state, loadingLabel, onSubmit }: ChatPanelProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    scrollerRef.current?.scrollTo({
      top: scrollerRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [state.messages, state.steps.length, state.isLoading])

  return (
    <div className="mx-auto flex min-h-[620px] w-full max-w-[920px] flex-col overflow-hidden rounded-[1.35rem] border border-white/[0.08] bg-[rgba(5,8,14,0.86)] shadow-[0_30px_110px_rgba(0,0,0,0.45)] backdrop-blur-xl">
      <StatusStrip state={state} />

      <div ref={scrollerRef} className="flex min-h-[380px] flex-1 flex-col gap-5 overflow-y-auto px-4 py-6 sm:px-6">
        {state.messages.length === 0 ? <EmptyChat onSubmit={onSubmit} /> : null}
        {state.messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {state.isLoading ? <LoadingBubble label={loadingLabel} /> : null}
      </div>

      <PromptInput query={query} setQuery={setQuery} state={state} onSubmit={onSubmit} />
    </div>
  )
}

function StatusStrip({ state }: { state: AgentState }) {
  const activeModel = state.config?.active_model?.label
  const fallbackCount = state.config?.fallback_models.length ?? 0
  const modelLabel = activeModel ?? modelStatusLabel(state.connectionStatus)
  const modelSummary =
    fallbackCount > 0
      ? `${modelLabel} +${fallbackCount} fallback${fallbackCount === 1 ? '' : 's'}`
      : modelLabel
  const tools = state.config?.tools ?? []

  return (
    <div className="flex flex-col gap-3 border-b border-white/[0.08] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <motion.span
          className={clsx(
            'h-2.5 w-2.5 rounded-full shadow-[0_0_16px_currentColor]',
            state.connectionStatus === 'online' ? 'bg-[var(--accent-cyan)] text-[var(--accent-cyan)]' : 'bg-[#60606b] text-[#60606b]',
          )}
          animate={state.isLoading ? { opacity: [1, 0.35, 1], scale: [1, 1.25, 1] } : undefined}
          transition={{ repeat: Infinity, duration: 1.1 }}
        />
        <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[#8a94a6]">
          {connectionStatusLabel(state.connectionStatus)}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[0.68rem] text-[#6f7888]">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 font-mono">
          <CircuitBoard className="h-3 w-3 text-[var(--accent-cyan)]" />
          {modelSummary}
        </span>
        {tools.slice(0, 3).map((tool) => (
          <span key={tool} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 font-mono">
            <Wrench className="h-3 w-3 text-[#fbbf24]" />
            {tool}
          </span>
        ))}
      </div>
    </div>
  )
}

function PromptInput({
  query,
  setQuery,
  state,
  onSubmit,
}: {
  query: string
  setQuery: (query: string) => void
  state: AgentState
  onSubmit: (query: string) => void
}) {
  return (
    <form
      className="border-t border-white/[0.08] p-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(query)
      }}
    >
      <div className="flex items-end gap-3 rounded-[1.1rem] border border-white/[0.09] bg-white/[0.045] p-2 focus-within:border-[var(--accent-border)] focus-within:bg-white/[0.065]">
        <Terminal className="mb-3 ml-2 h-4 w-4 flex-shrink-0 text-[#7d8590]" />
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
          className="max-h-[128px] min-h-[48px] flex-1 resize-none bg-transparent px-1 py-3 text-[0.95rem] leading-[1.45] text-white outline-none placeholder:text-[#6f7888] disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={state.isLoading || query.trim().length === 0}
          className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-full border border-white/15 bg-white text-black transition hover:scale-[1.03] disabled:cursor-not-allowed disabled:border-transparent disabled:bg-[#252832] disabled:text-[#747b8a]"
          aria-label="Send query"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </form>
  )
}

function EmptyChat({ onSubmit }: { onSubmit: (query: string) => void }) {
  return (
    <div className="m-auto flex w-full max-w-[620px] flex-col items-center gap-5 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/10 bg-white/[0.04]">
        <Sparkles className="h-5 w-5 text-[var(--accent-cyan)]" />
      </div>
      <div className="flex w-full flex-col gap-2">
        {suggestions.map((suggestion, index) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSubmit(suggestion)}
            className="group flex items-center justify-between gap-4 rounded-xl border border-white/[0.09] bg-white/[0.035] px-4 py-3 text-left font-mono text-[0.72rem] uppercase tracking-[0.08em] text-[#aab4c3] transition-colors hover:border-[var(--accent-border)] hover:bg-white/[0.065] hover:text-white"
          >
            <span className="text-[#667085]">0{index + 1}</span>
            <span className="flex-1 normal-case tracking-normal">{suggestion}</span>
            <ArrowUp className="h-3.5 w-3.5 rotate-45 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </button>
        ))}
      </div>
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  if (!message.content) return null

  const isUser = message.role === 'user'
  return (
    <motion.div
      className={clsx('flex w-full flex-col gap-1.5', isUser ? 'items-end' : 'items-start')}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
    >
      <p className="px-1 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[#667085]">
        {isUser ? 'You' : 'Agent'}
      </p>
      <div
        className={clsx(
          'max-w-[min(78ch,92%)] rounded-[1.15rem] border px-4 py-3 text-[0.93rem] leading-[1.68] text-[#edf2f8]',
          isUser
            ? 'border-white/[0.1] bg-white/[0.085] text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
            : 'border-cyan-300/[0.12] bg-[rgba(9,14,23,0.88)]',
        )}
      >
        {isUser ? <p className="whitespace-pre-line">{message.content}</p> : <MessageMarkdown content={message.content} />}
      </div>
    </motion.div>
  )
}

function LoadingBubble({ label }: { label: string }) {
  return (
    <div className="flex w-full items-start">
      <div className="rounded-[1.15rem] border border-cyan-300/[0.12] bg-[rgba(9,14,23,0.88)] px-4 py-3 text-[0.9rem] text-[#edf2f8]">
        <span className="flex items-center gap-2">
          <motion.span
            className="h-2 w-2 rounded-full bg-[var(--accent-cyan)] shadow-[0_0_18px_var(--accent-cyan)]"
            animate={{ opacity: [1, 0.35, 1], scale: [1, 1.45, 1] }}
            transition={{ repeat: Infinity, duration: 1.1, ease: 'easeInOut' }}
          />
          {label}
        </span>
      </div>
    </div>
  )
}

function modelStatusLabel(status: AgentState['connectionStatus']): string {
  const labels: Record<AgentState['connectionStatus'], string> = {
    checking: 'Detecting model...',
    online: 'No model configured',
    mock: 'Mock Mode',
    error: 'API Error',
  }
  return labels[status]
}

function connectionStatusLabel(status: AgentState['connectionStatus']): string {
  const labels: Record<AgentState['connectionStatus'], string> = {
    checking: 'Checking API',
    online: 'Agent Online',
    mock: 'Mock Mode',
    error: 'API Error',
  }
  return labels[status]
}
