import { useEffect, useState } from 'react'
import { ChatPanel } from './demo/ChatPanel'
import { TraceDock } from './demo/TraceDock'
import type { AgentState } from '../types'

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
    <section id="demo" className="relative overflow-hidden bg-[var(--bg-primary)] py-[10vh]">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--accent-cyan)]/20 to-transparent" />
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <SectionHeader
          kicker="Live Demo"
          title="Ask the agent"
          body="Type a research question. The answer streams in the chat while the reasoning trace stays available on demand."
        />

        <div className="mt-12">
          <ChatPanel
            query={query}
            setQuery={setQuery}
            state={state}
            loadingLabel={loadingLabels[loadingIndex]}
            onSubmit={submitQuery}
          />
        </div>
      </div>
      <TraceDock state={state} />
    </section>
  )
}

function SectionHeader({ kicker, title, body }: { kicker: string; title: string; body: string }) {
  return (
    <div className="mx-auto max-w-[920px]">
      <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
        {kicker}
      </p>
      <h2 className="mt-4 max-w-[12ch] text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[0.95] tracking-tight text-white">
        {title}
      </h2>
      <p className="mt-5 max-w-[42rem] text-[var(--text-secondary)] leading-[1.75]">{body}</p>
    </div>
  )
}
