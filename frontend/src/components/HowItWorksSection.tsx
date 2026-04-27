import { motion } from 'framer-motion'

const cards = [
  {
    index: '01',
    title: 'You ask',
    body: 'Your query hits the FastAPI endpoint, gets validated by Pydantic, rate-limited, and forwarded to the LangGraph agent state machine.',
  },
  {
    index: '02',
    title: 'Agent reasons',
    body: 'LangGraph runs the ReAct loop: the LLM emits a Thought, picks an Action, observes the result, then decides whether to continue or return a Final Answer. Max 10 iterations.',
  },
  {
    index: '03',
    title: 'Tools execute',
    body: 'Three sandboxed tools: web_search via Tavily API, python_executor with restricted eval(), and calculator. Each observation feeds back into the next reasoning step via SSE streaming.',
  },
]

const flowItems = ['User Query', 'FastAPI', 'LangGraph Agent', 'Tool Node', 'Agent Node', 'Final Answer']
const activeFlowItems = new Set(['LangGraph Agent', 'Tool Node', 'Agent Node'])

export function HowItWorksSection() {
  return (
    <section className="bg-black py-[12vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <p className="font-mono text-[0.72rem] uppercase tracking-[0.16em] text-[#6d6d6d]">
          Architecture
        </p>
        <h2 className="mt-4 text-[clamp(2.7rem,6vw,5.5rem)] font-semibold leading-[0.95] tracking-normal">
          How it thinks
        </h2>

        <div className="mt-14 grid grid-cols-1 gap-8 md:grid-cols-3 md:gap-0">
          {cards.map((card, index) => (
            <motion.article
              key={card.index}
              className="border-t border-[#181818] pt-5 md:pr-8"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1, duration: 0.45 }}
            >
              <p className="mb-4 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-[#666]">
                {card.index}
              </p>
              <h3 className="mb-4 text-[clamp(1.65rem,2.5vw,2.2rem)] font-semibold leading-[1] tracking-normal">
                {card.title}
              </h3>
              <p className="max-w-[24rem] leading-[1.75] text-[#9b9b9b]">{card.body}</p>
            </motion.article>
          ))}
        </div>

        <div className="mt-14 overflow-x-auto">
          <div className="flex min-w-max items-center">
            {flowItems.map((item, index) => (
              <div key={item} className="flex items-center">
                <span
                  className={`rounded border bg-white/[0.02] px-3 py-2 font-mono text-[0.65rem] uppercase tracking-[0.12em] ${
                    activeFlowItems.has(item)
                      ? 'border-[var(--accent-border)] text-[var(--accent-text)]'
                      : 'border-white/[0.08] text-[#9d9d9d]'
                  }`}
                >
                  {item}
                </span>
                {index < flowItems.length - 1 ? <span className="mx-2 text-[#444]">→</span> : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
