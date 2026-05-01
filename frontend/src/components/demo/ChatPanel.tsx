import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowUp, CircuitBoard, Lightbulb, Wrench } from 'lucide-react'
import clsx from 'clsx'
import type { AgentState, Message, Step } from '../../types'
import { ProjectMark } from '../ProjectMark'
import { MessageMarkdown } from './MessageMarkdown'
import { AnimatedAIChat } from '../ui/animated-ai-chat'

const starterSuggestions = [
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
  onClearHistory?: () => void
}

export function ChatPanel({ query, setQuery, state, loadingLabel, onSubmit, onClearHistory }: ChatPanelProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const liveSuggestions = contextualSuggestions(state)
  const canClearHistory = state.messages.length > 0 || state.steps.length > 0 || state.runSummary !== null
  const hasConversation = state.messages.length > 0 || state.steps.length > 0 || state.isLoading

  useEffect(() => {
    if (!hasConversation) {
      scrollerRef.current?.scrollTo({ top: 0 })
      return
    }

    scrollerRef.current?.scrollTo({
      top: scrollerRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [hasConversation, state.messages, state.steps.length, state.isLoading])

  return (
    <div className="relative mx-0 flex h-full min-h-0 min-w-0 w-full max-w-[100vw] flex-col overflow-hidden bg-[var(--bg-primary)] lg:mx-auto lg:max-w-[920px]">
      <StatusStrip state={state} />

      <div
        ref={scrollerRef}
        className={clsx(
          'flex min-h-0 min-w-0 flex-1 flex-col gap-5 overflow-x-hidden px-4 pt-4 sm:px-6 lg:px-8',
          hasConversation ? 'overflow-y-auto pb-6' : 'overflow-y-hidden pb-6',
        )}
      >
        {state.messages.length === 0 ? <EmptyChat onSubmit={onSubmit} /> : null}
        {state.messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {state.isLoading ? <ReasoningBubble label={loadingLabel} /> : null}
      </div>

      {state.messages.length > 0 && !state.isLoading ? (
        <PromptSuggestions suggestions={liveSuggestions} onSubmit={onSubmit} />
      ) : null}
      <PromptInput
        query={query}
        setQuery={setQuery}
        state={state}
        onSubmit={onSubmit}
        onClearHistory={onClearHistory}
        canClearHistory={canClearHistory}
      />
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
    <div className="flex flex-col gap-3 border-b border-[var(--border-subtle)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between lg:px-8">
      <div className="flex items-center gap-2.5">
        <motion.span
          className={clsx(
            'h-2 w-2 rounded-full shadow-[0_0_12px_currentColor]',
            state.connectionStatus === 'online' ? 'bg-[var(--accent-cyan)] text-[var(--accent-cyan)]' : 'bg-[var(--text-muted)] text-[var(--text-muted)]',
          )}
          animate={state.isLoading ? { opacity: [1, 0.4, 1], scale: [1, 1.2, 1] } : undefined}
          transition={{ repeat: Infinity, duration: 1.2 }}
        />
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          {connectionStatusLabel(state.connectionStatus)}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[0.65rem] text-[var(--text-tertiary)]">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono">
          <CircuitBoard className="h-3 w-3 text-[var(--accent-text)]" />
          {modelSummary}
        </span>
        {tools.slice(0, 3).map((tool) => (
          <span key={tool} className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono">
            <Wrench className="h-3 w-3 text-[var(--action)]" />
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
  onClearHistory,
  canClearHistory,
}: {
  query: string
  setQuery: (query: string) => void
  state: AgentState
  onSubmit: (query: string) => void
  onClearHistory?: () => void
  canClearHistory: boolean
}) {
  return (
    <>
      <AnimatedAIChat
        value={query}
        onValueChange={setQuery}
        onSubmit={onSubmit}
        disabled={state.isLoading}
        isLoading={state.isLoading}
        onClearHistory={onClearHistory}
        canClearHistory={canClearHistory}
      />
      <p className="mx-auto mt-2 max-w-[20rem] px-4 text-center text-[0.7rem] leading-5 text-[var(--text-tertiary)] sm:max-w-none">
        ReAct Agent can make mistakes. Verify important information.
      </p>
    </>
  )
}

function EmptyChat({ onSubmit }: { onSubmit: (query: string) => void }) {
  return (
    <div className="mx-0 flex min-h-full min-w-0 w-[calc(100vw-2rem)] max-w-[700px] flex-col items-center justify-center gap-4 py-4 text-center sm:w-full lg:mx-auto">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] shadow-[0_14px_42px_rgba(214,255,127,0.07)]">
        <ProjectMark className="h-5 w-5 text-[var(--accent-text)]" />
      </div>
      <div>
        <h1 className="max-w-[18rem] text-balance text-[1.55rem] font-semibold leading-tight text-[var(--text-primary)] sm:max-w-none sm:text-[2rem]">
          What should we reason through?
        </h1>
        <p className="mx-auto mt-2 max-w-[20rem] text-sm leading-6 text-[var(--text-secondary)] sm:max-w-[42rem]">
          Ask a question, inspect the ReAct loop, and watch each tool call earn its place.
        </p>
      </div>
      <div className="flex min-w-0 w-full flex-col gap-2">
        {starterSuggestions.map((suggestion, index) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSubmit(suggestion)}
            className="group flex min-h-12 min-w-0 items-center justify-between gap-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-4 py-2.5 text-left transition-colors hover:border-[var(--accent-border)] hover:bg-[var(--bg-tertiary)]"
          >
            <span className="font-mono text-[0.7rem] uppercase tracking-[0.1em] text-[var(--text-tertiary)]">
              {String(index + 1).padStart(2, '0')}
            </span>
            <span className="min-w-0 flex-1 break-words text-sm leading-5 text-[var(--text-secondary)]">{suggestion}</span>
            <ArrowUp className="h-4 w-4 rotate-45 text-[var(--text-tertiary)] transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[var(--accent-text)]" />
          </button>
        ))}
      </div>
    </div>
  )
}

function PromptSuggestions({
  suggestions,
  onSubmit,
}: {
  suggestions: string[]
  onSubmit: (query: string) => void
}) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return undefined

    function handlePointerDown(event: PointerEvent): void {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [open])

  return (
    <div className="relative z-30 flex justify-end px-3 pb-2 pt-2 sm:px-4 lg:px-8">
      <div>
        <div ref={menuRef} className="relative">
          <button
            type="button"
            aria-expanded={open}
            aria-haspopup="menu"
            onClick={() => setOpen((current) => !current)}
            className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)]/95 px-3 text-xs font-medium text-[var(--text-tertiary)] shadow-[0_14px_48px_rgba(0,0,0,0.32)] transition-colors hover:border-[var(--border-default)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-border)]"
          >
            <Lightbulb className="h-3.5 w-3.5 text-[var(--accent-text)]" />
            Suggestion prompts
          </button>

          {open ? (
            <motion.div
              role="menu"
              className="absolute bottom-full right-0 z-30 mb-2 w-[min(30rem,calc(100vw-2rem))] rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-1.5 shadow-[0_22px_80px_rgba(0,0,0,0.38)]"
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
            >
              <p className="px-2.5 py-2 font-mono text-[0.6rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                Suggestion prompts
              </p>
              <div className="flex flex-col gap-1">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={suggestion}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setOpen(false)
                      onSubmit(suggestion)
                    }}
                    className="group flex min-h-10 items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm leading-5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] focus-visible:bg-[var(--bg-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-border)]"
                  >
                    <span className="font-mono text-[0.62rem] text-[var(--text-tertiary)]">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="min-w-0 flex-1 break-words">{suggestion}</span>
                    <ArrowUp className="h-3.5 w-3.5 shrink-0 rotate-45 text-[var(--text-tertiary)] transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[var(--accent-text)]" />
                  </button>
                ))}
              </div>
            </motion.div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  if (!message.content) return null

  const isUser = message.role === 'user'
  return (
    <motion.div
      className={clsx('flex w-full flex-col gap-2', isUser ? 'items-end' : 'items-start')}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <p className="px-1 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[var(--text-tertiary)]">
        {isUser ? 'You' : 'Agent'}
      </p>
      <div
        className={clsx(
          'max-w-[min(72ch,92%)] rounded-2xl border px-4 py-3 text-[0.9375rem] leading-[1.7] text-[var(--text-secondary)]',
          isUser
            ? 'border-[var(--border-default)] bg-[var(--bg-secondary)] text-right'
            : 'border-[var(--border-subtle)] bg-[var(--bg-elevated)]',
        )}
      >
        {isUser ? <p className="whitespace-pre-line text-[var(--text-primary)]">{message.content}</p> : <MessageMarkdown content={message.content} />}
      </div>
    </motion.div>
  )
}

function ReasoningBubble({ label }: { label: string }) {
  return (
    <motion.div
      className="flex w-full items-start"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
    >
      <div className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-4 py-2 shadow-lg">
          <span className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
          <span className="grid h-7 w-8 place-items-center rounded-full bg-[var(--bg-tertiary)]">
            <ProjectMark className="h-3.5 w-3.5 text-[var(--accent-text)]" />
          </span>
          {label}
          <TypingDots />
        </span>
      </div>
    </motion.div>
  )
}

function TypingDots() {
  return (
    <span className="flex items-center">
      {[0, 1, 2].map((dot) => (
        <motion.span
          key={dot}
          className="mx-0.5 h-1.5 w-1.5 rounded-full bg-[var(--accent-text)]"
          initial={{ opacity: 0.3 }}
          animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.85, 1.08, 0.85] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: dot * 0.15, ease: 'easeInOut' }}
        />
      ))}
    </span>
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

function contextualSuggestions(state: AgentState): string[] {
  const userMessages = state.messages.filter((message) => message.role === 'user')
  const assistantMessages = state.messages.filter((message) => message.role === 'assistant')
  const lastUser = userMessages.at(-1)?.content ?? ''
  const lastAssistant = assistantMessages.at(-1)?.content ?? ''
  const contextText = `${lastUser} ${lastAssistant}`.toLowerCase()
  const tools = toolsFromState(state)
  const suggestions: string[] = []

  if (state.error || state.connectionStatus === 'error' || state.runSummary?.status === 'error') {
    suggestions.push('Diagnose the failed run and suggest the next concrete fix')
  }

  if (tools.has('web_search')) {
    suggestions.push('List the sources used and what each one contributed')
    suggestions.push('Extract the strongest source-backed claim from the last answer')
  } else if (/\b(search|source|sources|cite|citation|langgraph|documentation)\b/.test(contextText)) {
    suggestions.push('Search the web for sources that verify the last answer')
    suggestions.push('Check the last answer against current public documentation')
  } else if (/\b(latest|current|release)\b/.test(contextText)) {
    suggestions.push('Search the web to verify the current fact before answering')
  }

  if (tools.has('calculator') || /\b(calculate|sqrt|math|formula|equation)\b|\d/.test(lastUser.toLowerCase())) {
    suggestions.push('Verify the calculation and show the shortest path to the result')
  }

  if (tools.has('python_executor') || /\b(python|code|script|function|runtime|version)\b/.test(contextText)) {
    suggestions.push('Turn this into a small Python check I can run locally')
  }

  if (/\b(why|how|explain|reason|steps|trace)\b/.test(contextText) || state.steps.length > 0) {
    suggestions.push('Summarize the reasoning trace as a concise checklist')
  }

  suggestions.push(
    'Probe the weakest assumption in the last answer',
    'Turn the answer into a recruiter-facing project note',
    'Ask one follow-up that would prove the agent really understood the task',
  )

  return uniqueStrings(suggestions).slice(0, 3)
}

function toolsFromState(state: AgentState): Set<string> {
  const tools = new Set<string>()

  state.runSummary?.tools_used.forEach((tool) => tools.add(tool))
  state.steps.forEach((step) => {
    toolNamesFromStep(step).forEach((tool) => tools.add(tool))
  })

  return tools
}

function toolNamesFromStep(step: Step): string[] {
  return [step.tool, step.action, ...(step.tools_used ?? [])].filter(
    (tool): tool is string => typeof tool === 'string' && tool.length > 0,
  )
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values)]
}
