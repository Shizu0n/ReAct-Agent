import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Search, Terminal, Timer } from 'lucide-react'
import clsx from 'clsx'

const stages = [
  {
    key: 'thought',
    label: 'Thought',
    title: 'Classify the request',
    body: 'Current-fact question. Cached confidence is not evidence.',
    meta: 'needs source',
  },
  {
    key: 'action',
    label: 'Action',
    title: 'Call the search tool',
    body: 'web_search({ query: "Python latest stable release" })',
    meta: 'tool: web_search',
  },
  {
    key: 'observe',
    label: 'Observe',
    title: 'Read returned evidence',
    body: 'Release notes and dates replace model memory.',
    meta: 'sources parsed',
  },
  {
    key: 'final',
    label: 'Final',
    title: 'Answer with caveats',
    body: 'Summarize the version, cite the basis, flag uncertainty.',
    meta: 'ready',
  },
] as const

type StageKey = (typeof stages)[number]['key']

const stageIcon: Record<StageKey, typeof Timer> = {
  thought: Timer,
  action: Terminal,
  observe: Search,
  final: Check,
}

export function AgentFlowPreview() {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    const interval = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % stages.length)
    }, 1700)

    return () => window.clearInterval(interval)
  }, [])

  const activeStage = stages[activeIndex]
  const progress = ((activeIndex + 1) / stages.length) * 100

  return (
    <div className="agent-flow-shell" aria-label="Animated ReAct reasoning flow">
      <div className="agent-flow-status">
        <span className="agent-flow-status-dot" />
        <span>live run replay</span>
      </div>

      <div className="agent-flow-query">
        <span>User asks</span>
        <p>What changed in the latest Python release?</p>
      </div>

      <div className="agent-flow-progress" aria-hidden="true">
        <motion.span
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>

      <div className="agent-flow-thread">
        {stages.map((stage, index) => {
          const Icon = stageIcon[stage.key]
          const active = index === activeIndex
          const complete = index < activeIndex

          return (
            <motion.div
              key={stage.key}
              className={clsx(
                'agent-flow-step',
                `agent-flow-step-${stage.key}`,
                active && 'agent-flow-step-active',
                complete && 'agent-flow-step-complete',
              )}
              animate={{
                opacity: active ? 1 : complete ? 0.72 : 0.48,
                y: active ? -2 : 0,
              }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="agent-flow-step-marker">
                <Icon className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="agent-flow-step-head">
                  <span>{stage.label}</span>
                  <span>{stage.meta}</span>
                </div>
                <h3>{stage.title}</h3>
                <p>{stage.body}</p>
              </div>
            </motion.div>
          )
        })}
      </div>

      <div className="agent-flow-inspector">
        <span>Current frame</span>
        <AnimatePresence mode="wait">
          <motion.code
            key={activeStage.key}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
          >
            {activeStage.label.toLowerCase()} / {activeStage.meta}
          </motion.code>
        </AnimatePresence>
      </div>
    </div>
  )
}
