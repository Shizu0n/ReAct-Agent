import { motion } from 'framer-motion'
import { Brain, FileSearch, Network, ScrollText } from 'lucide-react'

const capabilities = [
  {
    icon: Brain,
    kicker: 'Memory',
    title: 'Remembers across conversations',
    body: 'Each conversation thread checkpoints its state in Postgres, while long-term facts are stored per user. Start a new chat and the agent still recalls what you told it — memory_read and memory_write appear as visible steps in the trace, not silent pipeline magic.',
  },
  {
    icon: FileSearch,
    kicker: 'RAG',
    title: 'Grounds answers in your documents',
    body: 'Upload a PDF or text file from the prompt bar. It is chunked, embedded, and stored in pgvector; answers cite the filename and chunk they came from. When the answer is not in your documents, the agent says so instead of fabricating one.',
  },
  {
    icon: ScrollText,
    kicker: 'Observability',
    title: 'Every run is replayable',
    body: 'Runs persist with their full reasoning trace: per-step timing, token usage, provider used, and any fallback events (e.g. Gemini failed → Groq). The History tab reopens any past conversation together with the reasoning that produced it.',
  },
  {
    icon: Network,
    kicker: 'MCP',
    title: 'Discovers tools at runtime',
    body: 'A companion MCP server is discovered over Streamable HTTP via tools/list. Discovered tools render in the trace identically to native ones, and the agent degrades cleanly when no server is configured.',
  },
]

export function CapabilitiesSection() {
  return (
    <section id="capabilities" className="border-t border-[var(--border-subtle)] bg-[var(--bg-primary)] py-[12vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
          Beyond the loop
        </p>
        <h2 className="mt-4 text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[0.95] tracking-tight text-white">
          What it demonstrates
        </h2>
        <p className="mt-6 max-w-[640px] text-[0.95rem] leading-[1.75] text-[var(--text-secondary)]">
          Four production-shaped agent capabilities, all running on free-tier quotas: persistent memory,
          document retrieval, replayable traces, and dynamic tool discovery.
        </p>

        <div className="mt-14 grid grid-cols-1 gap-8 md:grid-cols-2">
          {capabilities.map((capability, index) => (
            <motion.article
              key={capability.title}
              className="border-t border-[var(--border-subtle)] pt-5 md:pr-8"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.08, duration: 0.45 }}
            >
              <p className="flex items-center gap-2 font-mono text-[0.62rem] uppercase tracking-[0.14em] text-[var(--accent-text)]">
                <capability.icon className="h-3.5 w-3.5" />
                {capability.kicker}
              </p>
              <h3 className="mb-4 mt-3 text-[clamp(1.4rem,2.2vw,1.9rem)] font-semibold leading-[1.05] tracking-tight text-white">
                {capability.title}
              </h3>
              <p className="max-w-[30rem] leading-[1.75] text-[var(--text-secondary)]">{capability.body}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}
