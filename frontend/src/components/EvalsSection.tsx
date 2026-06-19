import { useEffect, useState } from 'react'

type CategoryScore = { total: number; answer_pass: number; tool_pass: number }

type EvalsBaseline = {
  generated_at: string
  model: { provider: string; label: string } | null
  summary: {
    total: number
    answer_pass: number
    tool_pass: number
    task_success_rate: number
    tool_selection_rate: number
    by_category: Record<string, CategoryScore>
  }
}

type EvalsPayload = EvalsBaseline | { status: 'unavailable' }

type LoadState =
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'ready'; data: EvalsBaseline }

function evalsUrl(): string {
  const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  const base = configured ? configured.replace(/\/$/, '') : '/api'
  return `${base}/evals`
}

function pct(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

export function EvalsSection() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false

    async function load(): Promise<void> {
      try {
        const response = await fetch(evalsUrl(), { headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error(String(response.status))
        const payload = (await response.json()) as EvalsPayload
        if (cancelled) return
        if ('status' in payload || !payload.summary) {
          setState({ kind: 'unavailable' })
          return
        }
        setState({ kind: 'ready', data: payload })
      } catch {
        if (!cancelled) setState({ kind: 'unavailable' })
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section id="evals" className="border-t border-[var(--border-subtle)] bg-[var(--bg-primary)] py-[8vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
          Measured, not claimed
        </p>
        <h2 className="mt-4 text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[0.95] tracking-tight text-white">
          How it scores
        </h2>
        <p className="mt-5 max-w-[640px] text-[0.95rem] leading-[1.7] text-[var(--text-secondary)]">
          A labelled eval suite runs the real agent end to end and scores two things that matter for a
          tool-using agent: did it reach the right answer, and did it pick the right tool (or correctly use
          none). Numbers below come from the committed baseline, not a hand-picked demo.
        </p>

        {state.kind === 'loading' ? (
          <p className="mt-12 font-mono text-[0.8rem] text-[var(--text-tertiary)]">Loading baseline…</p>
        ) : state.kind === 'unavailable' ? (
          <BaselinePending />
        ) : (
          <BaselineReady data={state.data} />
        )}
      </div>
    </section>
  )
}

function BaselinePending() {
  return (
    <div className="mt-12 rounded-2xl border border-dashed border-[var(--border-default)] bg-[var(--bg-secondary)] p-8">
      <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
        Baseline pending
      </p>
      <p className="mt-3 max-w-[620px] text-[0.9rem] leading-[1.7] text-[var(--text-secondary)]">
        No published baseline yet. The harness scores task success and tool selection across the labelled
        cases; run <code className="font-mono text-white">python -m evals.evaluate --publish</code> to generate
        and commit one, and these results fill in.
      </p>
    </div>
  )
}

function BaselineReady({ data }: { data: EvalsBaseline }) {
  const { summary } = data
  const categories = Object.entries(summary.by_category).sort(([a], [b]) => a.localeCompare(b))
  const generated = new Date(data.generated_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

  return (
    <div className="mt-12">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard
          label="Task success"
          value={pct(summary.task_success_rate)}
          detail={`${summary.answer_pass} / ${summary.total} cases reached the right answer`}
        />
        <StatCard
          label="Tool selection"
          value={pct(summary.tool_selection_rate)}
          detail={`${summary.tool_pass} / ${summary.total} cases used the expected tool`}
        />
      </div>

      <div className="mt-10">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          By category
        </p>
        <div className="mt-4">
          <div className="flex items-center justify-between gap-6 border-b border-[var(--border-subtle)] py-2 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
            <span>Category</span>
            <span className="flex gap-8">
              <span className="w-16 text-right">Answer</span>
              <span className="w-16 text-right">Tool</span>
            </span>
          </div>
          {categories.map(([name, score]) => (
            <div
              key={name}
              className="flex items-center justify-between gap-6 border-b border-[var(--border-subtle)] py-4"
            >
              <span className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-white">{name}</span>
              <span className="flex gap-8 font-mono text-[0.7rem] text-[var(--text-secondary)]">
                <span className="w-16 text-right text-white">
                  {score.answer_pass}/{score.total}
                </span>
                <span className="w-16 text-right text-white">
                  {score.tool_pass}/{score.total}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-6 font-mono text-[0.65rem] text-[var(--text-tertiary)]">
        {data.model ? `${data.model.label} · ` : ''}
        {summary.total} cases · baseline {generated}
      </p>
    </div>
  )
}

function StatCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-tertiary)] p-6">
      <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">{label}</p>
      <p className="mt-3 text-[clamp(2.25rem,4vw,3.25rem)] font-semibold leading-none text-white">{value}</p>
      <p className="mt-3 text-[0.8rem] leading-[1.6] text-[var(--text-secondary)]">{detail}</p>
    </div>
  )
}
