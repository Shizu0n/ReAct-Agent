import { motion } from 'framer-motion'

const cards = [
  {
    title: 'Request enters',
    body: 'FastAPI validates the message, keeps the recent chat context, and starts an SSE stream for live UI updates.',
  },
  {
    title: 'Graph loops',
    body: 'LangGraph alternates agent and tool nodes. Each pass emits Thought, Action, Observation, then decides whether to continue or finish.',
  },
  {
    title: 'Trace explains',
    body: 'The frontend renders every step as it arrives, so the chat answer is paired with the reasoning path that produced it.',
  },
]

const flowItems = ['User Query', 'FastAPI', 'Agent Node', 'Tool Node', 'Observation', 'Final Answer']
const activeFlowItems = new Set(['Agent Node', 'Tool Node', 'Observation'])

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="bg-[var(--bg-primary)] py-[12vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
          Request path
        </p>
        <h2 className="mt-4 text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[0.95] tracking-tight text-white">
          How it thinks
        </h2>

        <div className="mt-14 grid grid-cols-1 gap-8 md:grid-cols-3 md:gap-0">
          {cards.map((card, index) => (
            <motion.article
              key={card.title}
              className="border-t border-[var(--border-subtle)] pt-5 md:pr-8"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1, duration: 0.45 }}
            >
              <h3 className="mb-4 text-[clamp(1.5rem,2.5vw,2rem)] font-semibold leading-[1] tracking-tight text-white">
                {card.title}
              </h3>
              <p className="max-w-[24rem] leading-[1.75] text-[var(--text-secondary)]">{card.body}</p>
            </motion.article>
          ))}
        </div>

        <div className="mt-14 overflow-x-auto">
          <div className="flex min-w-max items-center gap-4">
            {flowItems.map((item, index) => (
              <div key={item} className="flex items-center">
                <span
                  className={`rounded-xl border px-3 py-2 font-mono text-[0.62rem] uppercase tracking-[0.12em] ${
                    activeFlowItems.has(item)
                      ? 'border-[var(--accent-border)] bg-[var(--accent-dim)] text-[var(--accent-text)]'
                      : 'border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                  }`}
                >
                  {item}
                </span>
                {index < flowItems.length - 1 ? (
                  <span className="mx-3 text-[var(--text-tertiary)]">/</span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
