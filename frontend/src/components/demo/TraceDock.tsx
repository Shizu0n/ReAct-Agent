import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tooltip from '@radix-ui/react-tooltip'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Clock, Minimize2, Route, Wrench, X } from 'lucide-react'
import clsx from 'clsx'
import type { AgentState, Step, StepType } from '../../types'

type TraceDockProps = {
  state: AgentState
}

export function TraceDock({ state }: TraceDockProps) {
  const [open, setOpen] = useState(false)
  const latestStep = state.steps.at(-1)
  const summary = state.runSummary
  const toolsUsed = summary?.tools_used.length ? summary.tools_used : distinctTools(state.steps)

  return (
    <Dialog.Root open={open} onOpenChange={setOpen} modal={false}>
      <Tooltip.Provider delayDuration={150}>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <Dialog.Trigger asChild>
              <button
                type="button"
                className="fixed bottom-24 right-5 z-40 flex h-12 w-12 items-center justify-center gap-3 rounded-full border border-[var(--border-default)] bg-[var(--bg-secondary)] font-mono text-[0.7rem] uppercase tracking-[0.12em] text-[var(--text-secondary)] shadow-xl transition-colors hover:border-[var(--accent-border)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] sm:bottom-5 sm:h-auto sm:w-auto sm:justify-start sm:px-4 sm:py-3"
                aria-label="Open reasoning trace"
              >
                <span className="relative grid h-8 w-8 place-items-center rounded-full border border-[var(--accent-border)] bg-[var(--accent-dim)]">
                  <Route className="h-4 w-4 text-[var(--accent-cyan)]" />
                  {state.isLoading ? <span className="absolute inset-0 rounded-full border border-[var(--accent-cyan)]/40 animate-ping" /> : null}
                </span>
                <span className="hidden sm:inline">Trace</span>
                <span className="hidden rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 text-[var(--text-tertiary)] sm:inline">
                  {state.steps.length}
                </span>
              </button>
            </Dialog.Trigger>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              side="left"
              className="z-50 rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] px-3 py-2 text-xs text-[var(--text-secondary)] shadow-xl"
            >
              Open reasoning timeline
              <Tooltip.Arrow className="fill-[var(--bg-secondary)]" />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      </Tooltip.Provider>

      <Dialog.Portal>
        <Dialog.Content className="fixed inset-x-3 bottom-3 z-50 max-h-[82vh] overflow-hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-secondary)] shadow-2xl data-[state=open]:animate-in data-[state=closed]:animate-out sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[540px]">
          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
            <div>
              <Dialog.Title className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-primary)]">
                Reasoning Trace
              </Dialog.Title>
              <p className="mt-1 font-mono text-[0.6rem] text-[var(--text-tertiary)]">
                {summary?.elapsed_ms ? `${summary.elapsed_ms}ms` : state.isLoading ? 'streaming' : 'idle'}
                {summary?.run_id ? ` · ${summary.run_id.slice(0, 8)}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="grid h-11 w-11 place-items-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] transition hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  aria-label="Minimize reasoning trace"
                >
                  <Minimize2 className="h-4 w-4" />
                </button>
              </Dialog.Close>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="grid h-11 w-11 place-items-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] transition hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  aria-label="Close reasoning trace"
                >
                  <X className="h-4 w-4" />
                </button>
              </Dialog.Close>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 border-b border-[var(--border-subtle)] p-4">
            <Metric icon={<Activity className="h-3.5 w-3.5" />} label="steps" value={String(state.steps.length)} />
            <Metric icon={<Wrench className="h-3.5 w-3.5" />} label="tools" value={toolsUsed.length ? toolsUsed.join(', ') : 'none'} />
            <Metric icon={<Clock className="h-3.5 w-3.5" />} label="latest" value={latestStep ? stepLabel(stepType(latestStep)) : 'idle'} />
          </div>

          <div className="max-h-[58vh] overflow-y-auto p-4">
            {state.steps.length === 0 && !state.isLoading ? (
              <div className="grid min-h-[260px] place-items-center whitespace-pre-line text-center font-mono text-[0.75rem] leading-[1.6] text-[var(--text-tertiary)]">
                {'Run a query to see\nthe agent reasoning'}
              </div>
            ) : (
              <Timeline steps={state.steps} latestKey={latestStep ? stepKey(latestStep) : undefined} />
            )}
            {state.error ? <ErrorCard error={state.error} /> : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Timeline({ steps, latestKey }: { steps: Step[]; latestKey?: string }) {
  const progressHeight = useMemo(() => `${Math.max(0, steps.length - 1) * 84 + 20}px`, [steps.length])

  return (
    <div className="relative">
      <motion.div
        className="absolute left-[18px] top-5 w-px bg-gradient-to-b from-[var(--accent-cyan)] via-[var(--border-strong)] to-transparent"
        initial={{ height: 0 }}
        animate={{ height: progressHeight }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
      />
      <AnimatePresence initial={false}>
        {steps.map((step) => (
          <TraceStep key={stepKey(step)} step={step} active={stepKey(step) === latestKey} />
        ))}
      </AnimatePresence>
    </div>
  )
}

function TraceStep({ step, active }: { step: Step; active: boolean }) {
  return (
    <motion.div
      layout
      className="relative pb-3 pl-10"
      initial={{ opacity: 0, x: 18, filter: 'blur(6px)' }}
      animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.3 }}
    >
      <span className={clsx('absolute left-0 top-3 h-9 w-9 rounded-full border bg-[var(--bg-secondary)]', dotClass(stepType(step)), active && 'shadow-[0_0_20px_currentColor]')} />
      <div
        className={clsx(
          'rounded-xl border bg-[var(--bg-tertiary)]/50 p-3 transition-colors',
          active ? 'border-[var(--accent-border)] bg-[var(--accent-dim)]' : 'border-[var(--border-subtle)]',
        )}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[var(--bg-tertiary)] px-2 py-0.5 font-mono text-[0.6rem] text-[var(--text-tertiary)]">
            #{String(step.step).padStart(2, '0')}
          </span>
          <span className={clsx('rounded-full px-2 py-0.5 font-mono text-[0.6rem]', badgeClass(stepType(step)))}>
            {stepLabel(stepType(step))}
          </span>
          <span className="ml-auto font-mono text-[0.55rem] text-[var(--text-tertiary)]">{formatTime(step.timestamp)}</span>
        </div>
        <p className="whitespace-pre-line text-[0.8rem] leading-[1.6] text-[var(--text-secondary)]">{stepContent(step)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {toolName(step) ? <TraceMeta label="tool" value={toolName(step)!} /> : null}
          {step.action_input ? <TraceMeta label="input" value={step.action_input} /> : null}
          {step.elapsed_ms ? <TraceMeta label="elapsed" value={`${step.elapsed_ms}ms`} /> : null}
        </div>
      </div>
    </motion.div>
  )
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]/50 p-3">
      <div className="mb-2 flex items-center gap-2 font-mono text-[0.55rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
        <span className="text-[var(--accent-cyan)]">{icon}</span>
        {label}
      </div>
      <p className="truncate font-mono text-[0.7rem] text-[var(--text-secondary)]" title={value}>
        {value}
      </p>
    </div>
  )
}

function TraceMeta({ label, value }: { label: string; value: string }) {
  return (
    <span className="max-w-full truncate rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2 py-1 font-mono text-[0.6rem] text-[var(--text-tertiary)]" title={value}>
      {label}: {value}
    </span>
  )
}

function ErrorCard({ error }: { error: string }) {
  return (
    <div className="mt-3 rounded-xl border border-[var(--error)]/30 bg-[var(--error-dim)] p-3 text-red-300">
      <span className="rounded-full border border-red-500/30 px-2 py-0.5 font-mono text-[0.6rem]">
        ERROR
      </span>
      <p className="mt-2 text-[0.8rem] leading-[1.6]">{error}</p>
    </div>
  )
}

function distinctTools(steps: Step[]): string[] {
  return Array.from(new Set(steps.map(toolName).filter((tool): tool is string => Boolean(tool))))
}

function stepKey(step: Step): string {
  return `${stepType(step)}-${step.step}-${step.timestamp}-${stepContent(step).slice(0, 12)}`
}

function stepType(step: Step): StepType {
  return step.type ?? (step.action ? 'action' : 'final')
}

function stepContent(step: Step): string {
  return step.content ?? step.observation ?? step.thought ?? ''
}

function toolName(step: Step): string | undefined {
  return step.tool ?? step.action ?? undefined
}

function stepLabel(type: StepType): string {
  return type === 'observation' ? 'OBSERVE' : type.toUpperCase()
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return date.toLocaleTimeString([], { hour12: false })
}

function dotClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border-[var(--accent-border)] text-[var(--accent-cyan)]',
    action: 'border-amber-500/40 text-amber-400',
    observation: 'border-emerald-500/40 text-emerald-400',
    final: 'border-[var(--border-strong)] text-white',
  }
  return classes[type]
}

function badgeClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border border-[var(--accent-border)] text-[var(--accent-text)] bg-[var(--accent-dim)]',
    action: 'border border-amber-500/40 text-amber-400 bg-amber-500/10',
    observation: 'border border-emerald-500/40 text-emerald-400 bg-emerald-500/10',
    final: 'border border-[var(--border-strong)] text-white bg-white/5',
  }
  return classes[type]
}
