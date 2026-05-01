import { motion } from 'framer-motion'
import { ArrowRight, Code2, Route } from 'lucide-react'
import { AgentFlowPreview } from './hero/AgentFlowPreview'

type HeroSectionProps = {
  onOpenChat: () => void
}

export function HeroSection({ onOpenChat }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden border-b border-[var(--border-subtle)] bg-[var(--bg-primary)] px-[clamp(1.25rem,4vw,3rem)] py-[clamp(5rem,10vh,7rem)]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:48px_48px]" />

      <div className="relative mx-auto grid min-h-[calc(100vh-10rem)] max-w-[1360px] grid-cols-1 items-center gap-12 lg:grid-cols-[0.88fr_1.12fr] lg:gap-16">
        <motion.div
          className="flex flex-col justify-center gap-7"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-3 py-1.5 font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
            <Route className="h-3 w-3 text-[var(--accent-text)]" />
            ML Engineering / ReAct loop
          </span>

          <div>
            <h1 className="max-w-[13ch] text-[clamp(3.35rem,6.2vw,6.15rem)] font-semibold leading-[0.92] tracking-normal text-[var(--text-primary)] lg:max-w-[11ch]">
              Agent that shows its work.
            </h1>
            <p className="mt-6 max-w-[52ch] text-[clamp(1rem,1.5vw,1.125rem)] leading-[1.75] text-[var(--text-secondary)]">
              A LangGraph ReAct agent with a modern chat surface and a visible Thought, Action,
              Observe trace. The point is not vibes. The point is inspectable reasoning.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onOpenChat}
              className="group flex items-center gap-2 rounded-xl bg-[var(--accent)] px-6 py-3.5 font-medium text-black transition-all duration-300 hover:bg-[var(--accent-text)]"
            >
              Open chat
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <a
              href="https://github.com/Shizu0n/react-agent"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl border border-[var(--border-default)] bg-[var(--bg-secondary)] px-5 py-3.5 font-medium text-[var(--text-secondary)] transition-all hover:border-[var(--border-strong)] hover:text-white"
            >
              <Code2 className="h-4 w-4" />
              Source
            </a>
          </div>
        </motion.div>

        <motion.div
          className="flex items-center justify-center"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.7 }}
        >
          <AgentFlowPreview />
        </motion.div>
      </div>
    </section>
  )
}
