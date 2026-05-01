import type { ReactNode } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Check, Clock, Route, Search, Terminal, Timer, Wrench, X } from 'lucide-react'
import clsx from 'clsx'
import type { AgentState, Step, StepType } from '../../types'

type ReasoningPanelProps = {
  state: AgentState
  open: boolean
  width: number
  mobileOpen: boolean
  onOpenChange: (open: boolean) => void
  onStartResize: (event: ReactPointerEvent<HTMLDivElement>) => void
  onMobileOpenChange: (open: boolean) => void
}

const traceIcon: Record<StepType, typeof Timer> = {
  thought: Timer,
  action: Terminal,
  observation: Search,
  final: Check,
}

export function ReasoningPanel({
  state,
  open,
  width,
  mobileOpen,
  onOpenChange,
  onStartResize,
  onMobileOpenChange,
}: ReasoningPanelProps) {
  return (
    <>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.aside
            className="relative hidden h-dvh shrink-0 flex-col border-l border-[var(--border-subtle)] bg-[var(--bg-secondary)] xl:flex"
            style={{ width }}
            initial={{ x: 32, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 32, opacity: 0 }}
            transition={{ duration: 0.24, ease: 'easeOut' }}
          >
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize reasoning trace"
              className="absolute left-0 top-0 z-10 hidden h-full w-2 -translate-x-1 cursor-col-resize touch-none xl:block"
              onPointerDown={onStartResize}
            >
              <span className="mx-auto block h-full w-px bg-transparent transition-colors hover:bg-[var(--accent-border)]" />
            </div>
            <PanelChrome
              state={state}
              onClose={() => onOpenChange(false)}
            />
          </motion.aside>
        ) : null}
      </AnimatePresence>

      <Dialog.Root open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(5,5,6,0.62)] xl:hidden" />
          <Dialog.Content
            className="fixed inset-x-2 bottom-2 z-50 max-h-[82vh] overflow-hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-secondary)] shadow-2xl xl:hidden"
          >
            <Dialog.Title className="sr-only">Reasoning Trace</Dialog.Title>
            <Dialog.Description className="sr-only">
              Live thought, action, observation, and final answer steps for the current agent run.
            </Dialog.Description>
            <PanelChrome
              state={state}
              onClose={() => onMobileOpenChange(false)}
              compact
            />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}

function PanelChrome({
  state,
  compact = false,
  onClose,
}: {
  state: AgentState
  compact?: boolean
  onClose: () => void
}) {
  const latestStep = state.steps.at(-1)
  const summary = state.runSummary
  const toolsUsed = summary?.tools_used.length ? summary.tools_used : distinctTools(state.steps)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
        <div>
          <h2 className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-[var(--text-primary)]">
            Reasoning Trace
          </h2>
          <p className="mt-1 font-mono text-[0.6rem] text-[var(--text-tertiary)]">
            {summary?.elapsed_ms ? `${summary.elapsed_ms}ms` : state.isLoading ? 'streaming' : 'idle'}
            {summary?.run_id ? ` / ${summary.run_id.slice(0, 8)}` : ''}
          </p>
        </div>
        {compact ? (
          <button
            type="button"
            onClick={onClose}
            className="grid h-11 w-11 place-items-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-tertiary)] transition hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            aria-label="Close reasoning trace"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <TelemetryStrip
        elapsed={summary?.elapsed_ms}
        isLoading={state.isLoading}
        latest={latestStep ? stepLabel(stepType(latestStep)) : 'idle'}
        steps={state.steps.length}
        tools={toolsUsed}
      />
      <TraceProgress current={state.steps.length} total={Math.max(state.steps.length, state.isLoading ? state.steps.length + 1 : state.steps.length)} />

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {state.steps.length === 0 && !state.isLoading ? (
          <div className="grid min-h-[320px] place-items-center text-center">
            <div>
              <Route className="mx-auto h-8 w-8 text-[var(--text-muted)]" />
              <p className="mt-4 whitespace-pre-line font-mono text-[0.75rem] leading-[1.6] text-[var(--text-tertiary)]">
                {'Run a query to see\nThought / Action / Observe'}
              </p>
            </div>
          </div>
        ) : (
          <Timeline steps={state.steps} latestKey={latestStep ? stepKey(latestStep) : undefined} />
        )}
        {state.error ? <ErrorCard error={state.error} /> : null}
      </div>
    </div>
  )
}

function Timeline({ steps, latestKey }: { steps: Step[]; latestKey?: string }) {
  return (
    <div className="relative space-y-3">
      <AnimatePresence initial={false}>
        {steps.map((step, index) => (
          <TraceStep
            key={stepKey(step)}
            step={step}
            active={stepKey(step) === latestKey}
            displayIndex={index + 1}
            isLast={index === steps.length - 1}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}

function TraceStep({
  step,
  active,
  displayIndex,
  isLast,
}: {
  step: Step
  active: boolean
  displayIndex: number
  isLast: boolean
}) {
  const type = stepType(step)
  const Icon = traceIcon[type]
  const cycle = Number.isFinite(step.step) ? `cycle ${String(step.step).padStart(2, '0')}` : 'cycle --'

  return (
    <motion.div
      layout
      className="relative grid grid-cols-[28px_1fr] gap-3"
      initial={{ opacity: 0, x: 16, filter: 'blur(5px)' }}
      animate={{ opacity: active ? 1 : 0.72, x: 0, y: active ? -2 : 0, filter: 'blur(0px)' }}
      exit={{ opacity: 0, x: 10 }}
      transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative pt-3">
        {!isLast ? (
          <span
            aria-hidden="true"
            className={clsx(
              'absolute left-1/2 top-8 h-[calc(100%+0.75rem)] w-px -translate-x-1/2',
              lineClass(type),
            )}
          />
        ) : null}
        <span
          aria-hidden="true"
          className={clsx(
            'relative z-10 grid h-7 w-7 place-items-center rounded-full border bg-[var(--bg-secondary)]',
            dotClass(type),
            active && 'ring-2 ring-[var(--accent-border)] shadow-[0_0_18px_currentColor]',
          )}
        >
          {active ? <span className="absolute h-full w-full animate-ping rounded-full border border-current opacity-35" /> : null}
          <Icon className="relative h-3.5 w-3.5" />
        </span>
      </div>
      <div
        aria-current={active ? 'step' : undefined}
        className={clsx(
          'min-w-0 rounded-xl border bg-[var(--bg-tertiary)]/45 p-3 transition-[background-color,border-color,box-shadow] duration-200',
          active ? activeCardClass(type) : 'border-[var(--border-subtle)]',
        )}
      >
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[0.58rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
            {String(displayIndex).padStart(2, '0')}
          </span>
          <span className={clsx('rounded-full px-2 py-0.5 font-mono text-[0.6rem]', badgeClass(type))}>
            {stepLabel(type)}
          </span>
          <span className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-2 py-0.5 font-mono text-[0.56rem] uppercase tracking-[0.08em] text-[var(--text-tertiary)]">
            {cycle}
          </span>
          <span className="ml-auto font-mono text-[0.55rem] text-[var(--text-tertiary)]">{formatTime(step.timestamp)}</span>
        </div>
        <p className="whitespace-pre-line break-words text-[0.82rem] leading-[1.65] text-[var(--text-secondary)]">{stepContent(step)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {toolName(step) ? <TraceMeta label="tool" value={toolName(step)!} /> : null}
          {step.action_input ? <TraceMeta label="input" value={step.action_input} /> : null}
          {step.elapsed_ms ? <TraceMeta label="elapsed" value={`${step.elapsed_ms}ms`} /> : null}
        </div>
      </div>
    </motion.div>
  )
}

function TraceProgress({ current, total }: { current: number; total: number }) {
  const progress = total > 0 ? Math.min(100, Math.max(0, (current / total) * 100)) : 0

  return (
    <div className="border-b border-[var(--border-subtle)] px-4 py-0">
      <div className="h-px overflow-hidden bg-[var(--border-subtle)]">
        <motion.span
          className="block h-full rounded-full bg-gradient-to-r from-[var(--thought)] via-[var(--action)] to-[var(--accent)] shadow-[0_0_18px_rgba(214,255,127,0.2)]"
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  )
}

function TelemetryStrip({
  elapsed,
  isLoading,
  latest,
  steps,
  tools,
}: {
  elapsed?: number
  isLoading: boolean
  latest: string
  steps: number
  tools: string[]
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-[var(--border-subtle)] px-4 py-3">
      <TelemetryItem icon={<Activity className="h-3.5 w-3.5" />} label="steps" value={String(steps)} />
      <TelemetryItem icon={<Wrench className="h-3.5 w-3.5" />} label="tools" value={tools.length ? tools.join(', ') : 'none'} />
      <TelemetryItem icon={<Clock className="h-3.5 w-3.5" />} label="time" value={elapsed ? `${elapsed}ms` : isLoading ? 'streaming' : 'idle'} />
      <TelemetryItem label="latest" value={latest} />
    </div>
  )
}

function TelemetryItem({ icon, label, value }: { icon?: ReactNode; label: string; value: string }) {
  return (
    <div className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)]/55 px-2.5 py-1.5 font-mono">
      {icon ? <span className="shrink-0 text-[var(--accent-text)]">{icon}</span> : null}
      <span className="shrink-0 text-[0.55rem] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
        {label}
      </span>
      <span className="truncate text-[0.65rem] text-[var(--text-secondary)]" title={value}>
        {value}
      </span>
    </div>
  )
}

function TraceMeta({ label, value }: { label: string; value: string }) {
  return (
    <span className="max-w-full truncate rounded-full border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-2 py-1 font-mono text-[0.6rem] text-[var(--text-tertiary)]" title={value}>
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
    thought: 'border-[var(--thought-border)] text-[var(--thought)]',
    action: 'border-[var(--action-border)] text-[var(--action)]',
    observation: 'border-[var(--observation-border)] text-[var(--observation)]',
    final: 'border-[var(--border-strong)] text-white',
  }
  return classes[type]
}

function lineClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'bg-gradient-to-b from-[var(--thought)] to-[var(--border-subtle)]',
    action: 'bg-gradient-to-b from-[var(--action)] to-[var(--border-subtle)]',
    observation: 'bg-gradient-to-b from-[var(--observation)] to-[var(--border-subtle)]',
    final: 'bg-[var(--border-subtle)]',
  }
  return classes[type]
}

function badgeClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border border-[var(--thought-border)] text-[var(--thought)] bg-[var(--thought-dim)]',
    action: 'border border-[var(--action-border)] text-[var(--action)] bg-[var(--action-dim)]',
    observation: 'border border-[var(--observation-border)] text-[var(--observation)] bg-[var(--observation-dim)]',
    final: 'border border-[var(--border-strong)] text-[var(--text-primary)] bg-white/5',
  }
  return classes[type]
}

function activeCardClass(type: StepType): string {
  const classes: Record<StepType, string> = {
    thought: 'border-[var(--thought-border)] bg-[var(--thought-dim)] shadow-[0_16px_42px_rgba(139,211,255,0.07)]',
    action: 'border-[var(--action-border)] bg-[var(--action-dim)] shadow-[0_16px_42px_rgba(246,193,119,0.07)]',
    observation: 'border-[var(--observation-border)] bg-[var(--observation-dim)] shadow-[0_16px_42px_rgba(126,231,135,0.07)]',
    final: 'border-[var(--border-strong)] bg-white/5 shadow-[0_16px_42px_rgba(255,255,255,0.04)]',
  }
  return classes[type]
}
