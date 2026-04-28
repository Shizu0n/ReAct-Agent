import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowDown, Activity } from 'lucide-react'
import { AgentFlowPreview } from './hero/AgentFlowPreview'
import { ScrollCue } from './hero/ScrollCue'

const badges = ['Python 3.11', 'LangGraph', 'FastAPI', 'SSE Streaming']

export function HeroSection() {
  const [cueHidden, setCueHidden] = useState(false)

  function scrollToDemo(): void {
    setCueHidden(true)
    document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section className="relative min-h-screen overflow-hidden bg-[#020304] px-[clamp(1.25rem,4vw,3rem)] py-[clamp(5rem,10vh,7rem)]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:72px_72px] opacity-40" />
      <div className="relative mx-auto grid min-h-[calc(100vh-10rem)] max-w-[1320px] grid-cols-1 items-center gap-12 lg:grid-cols-[0.92fr_1.08fr] lg:gap-16">
        <motion.div
          className="flex flex-col justify-center gap-8"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="inline-flex w-fit items-center gap-2 font-mono text-[0.72rem] uppercase tracking-[0.18em] text-[#7d8590]">
            <Activity className="h-3.5 w-3.5 text-[var(--accent-cyan)]" />
            ML Engineering · Project 01
          </span>

          <h1 className="flex flex-col font-sans text-[clamp(3.8rem,8.6vw,8.7rem)] font-bold leading-[0.86] tracking-normal">
            <span className="text-white">ReAct</span>
            <span className="italic text-[#a1a1aa]">Agent</span>
          </h1>

          <p className="max-w-[42ch] text-[clamp(1rem,1.5vw,1.12rem)] leading-[1.78] text-[#a1a1aa]">
            A reasoning agent built with LangGraph that breaks complex queries into Thought, Action,
            Observation loops, executing real tools to reach verified answers.
          </p>

          <div className="flex flex-wrap gap-2">
            {badges.map((badge) => (
              <span
                key={badge}
                className="rounded-full border border-white/10 bg-white/[0.045] px-3 py-1 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[#aeb7c2] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
              >
                {badge}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={scrollToDemo}
            className="group flex w-fit items-center gap-3 border border-white/15 bg-white/[0.03] px-5 py-3 font-mono text-[0.72rem] uppercase tracking-[0.16em] text-white transition-all duration-300 hover:border-white hover:bg-white hover:text-black hover:shadow-[0_0_34px_rgba(56,189,248,0.18)]"
          >
            Try the demo
            <ArrowDown className="h-4 w-4 transition-transform group-hover:translate-y-0.5" />
          </button>
        </motion.div>

        <motion.div
          className="hidden min-h-[520px] items-center justify-center lg:flex"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.7 }}
        >
          <AgentFlowPreview />
        </motion.div>
      </div>

      <ScrollCue hidden={cueHidden} />
    </section>
  )
}
