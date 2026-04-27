import { motion } from 'framer-motion'

const badges = ['Python 3.11', 'LangGraph', 'FastAPI', 'SSE Streaming']

export function HeroSection() {
  function scrollToDemo(): void {
    document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section className="relative grid min-h-screen grid-cols-1 gap-12 px-[clamp(1.25rem,4vw,3rem)] py-[clamp(5rem,10vh,7rem)] lg:grid-cols-[1fr_1fr] lg:gap-16">
      <motion.div
        className="flex flex-col justify-center gap-8"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <span className="font-mono text-[0.72rem] uppercase tracking-[0.18em] text-[#7d7d7d]">
          ML Engineering · Project 01
        </span>

        <h1 className="flex flex-col font-sans text-[clamp(3.5rem,8.4vw,8rem)] font-bold leading-[0.9] tracking-normal">
          <span className="text-white">ReAct</span>
          <span className="italic text-[#9f9f9f]">Agent</span>
        </h1>

        <p className="max-w-[38ch] text-[clamp(1rem,1.5vw,1.08rem)] leading-[1.75] text-[#9d9d9d]">
          A reasoning agent built with LangGraph that breaks complex queries into Thought, Action,
          Observation loops, executing real tools to reach verified answers.
        </p>

        <div className="flex flex-wrap gap-2">
          {badges.map((badge) => (
            <span
              key={badge}
              className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[#9d9d9d]"
            >
              {badge}
            </span>
          ))}
        </div>

        <button
          type="button"
          onClick={scrollToDemo}
          className="self-start border border-[#262626] bg-transparent px-5 py-3 font-mono text-[0.72rem] uppercase tracking-[0.16em] text-white transition-all duration-300 hover:border-white hover:bg-white hover:text-black hover:shadow-[0_0_24px_rgba(99,102,241,0.25)]"
        >
          Try the demo ↓
        </button>
      </motion.div>

      <div className="hidden items-center justify-center lg:flex">
        <svg width="400" height="400" viewBox="0 0 400 400" className="opacity-70">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="8"
              refX="6"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L0,6 L6,3 z" fill="rgba(255,255,255,0.25)" />
            </marker>
          </defs>

          <motion.g
            className="svg-origin-center"
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 24, ease: 'linear' }}
          >
            <path
              d="M176 102 L116 260"
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1"
              fill="none"
              markerEnd="url(#arrowhead)"
            />
            <path
              d="M150 280 L242 280"
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1"
              fill="none"
              markerEnd="url(#arrowhead)"
            />
            <path
              d="M284 260 L224 102"
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1"
              fill="none"
              markerEnd="url(#arrowhead)"
            />
          </motion.g>

          <DiagramNode x={145} y={61} width={110} label="THOUGHT" />
          <DiagramNode x={50} y={261} width={100} label="ACTION" />
          <DiagramNode x={245} y={261} width={110} label="OBSERVE" />

          <motion.circle
            cx="200"
            cy="200"
            r="28"
            fill="rgba(99,102,241,0.08)"
            stroke="rgba(99,102,241,0.3)"
            animate={{ scale: [1, 1.08, 1], opacity: [0.7, 1, 0.7] }}
            transition={{ repeat: Infinity, duration: 2.4, ease: 'easeInOut' }}
            className="svg-origin-center"
          />
          <text
            x="200"
            y="204"
            fontFamily="JetBrains Mono"
            fontSize="10"
            fill="#a5b4fc"
            textAnchor="middle"
          >
            LLM
          </text>
        </svg>
      </div>

      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-[#666]"
        animate={{ y: [0, 6, 0] }}
        transition={{ repeat: Infinity, duration: 1.8 }}
      >
        Scroll ↓
      </motion.div>
    </section>
  )
}

function DiagramNode({
  x,
  y,
  width,
  label,
}: {
  x: number
  y: number
  width: number
  label: string
}) {
  return (
    <g className="transition-colors">
      <rect
        x={x}
        y={y}
        width={width}
        height="38"
        rx="4"
        fill="rgba(255,255,255,0.04)"
        stroke="rgba(99,102,241,0.3)"
        strokeWidth="1"
      />
      <text
        x={x + width / 2}
        y={y + 24}
        fontFamily="JetBrains Mono"
        fontSize="11"
        fill="#6366f1"
        textAnchor="middle"
      >
        {label}
      </text>
    </g>
  )
}
