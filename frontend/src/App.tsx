import { type FormEvent, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Brain,
  Calculator,
  CheckCircle2,
  Code2,
  Loader2,
  Menu,
  MessageSquare,
  PanelRight,
  Plus,
  Search,
  Send,
  Sparkles,
  Terminal,
  Timer,
  Wrench,
  X,
} from 'lucide-react'

type Step = {
  thought: string
  action: string
  action_input: string
  observation: string
  timestamp: string
}

type AgentResponse = {
  result?: string
  trace?: Step[]
  total_time?: number
  run_id: string
  answer?: string
  steps?: Step[]
  tools_used?: string[]
  latency_ms?: number
  status?: string
}

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: 'preview' | 'success' | 'error'
}

type Conversation = {
  id: string
  title: string
  subtitle: string
  messages: Message[]
  steps: Step[]
  toolsUsed: string[]
  latencyMs: number | null
  status: 'idle' | 'running' | 'success' | 'error'
  runId?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const quickPrompts = [
  'Search the latest AI agent trends and summarize them.',
  'Calculate the compound growth of $10,000 at 8% for 5 years.',
  'Use Python to calculate the mean, median, and standard deviation of [12, 18, 21, 25, 31].',
]

const starterSteps: Step[] = [
  {
    thought: 'Need a deterministic calculation instead of estimating.',
    action: 'calculator',
    action_input: '10000 * (1 + 0.08) ** 5',
    observation: '14693.280768000006',
    timestamp: 'preview',
  },
  {
    thought: 'Translate the numeric result into a readable answer.',
    action: 'final',
    action_input: 'compound growth summary',
    observation: 'The investment grows to about $14,693.28 after 5 years.',
    timestamp: 'preview',
  },
]

const initialConversation: Conversation = {
  id: 'preview-compound-growth',
  title: 'Compound growth',
  subtitle: 'calculator -> final answer',
  messages: [
    {
      id: 'm1',
      role: 'user',
      content: quickPrompts[1],
    },
    {
      id: 'm2',
      role: 'assistant',
      content:
        'The investment grows to about $14,693.28 after 5 years. The trace shows the calculator tool call that produced the number.',
      status: 'preview',
    },
  ],
  steps: starterSteps,
  toolsUsed: ['calculator'],
  latencyMs: 842,
  status: 'idle',
}

const initialHistory: Conversation[] = [
  initialConversation,
  {
    ...emptyConversation('agent-trends', 'AI agent trends'),
    subtitle: 'web_search planned',
    messages: [
      {
        id: 'm3',
        role: 'user',
        content: quickPrompts[0],
      },
    ],
  },
  {
    ...emptyConversation('python-stats', 'Python stats'),
    subtitle: 'python_executor planned',
    messages: [
      {
        id: 'm4',
        role: 'user',
        content: quickPrompts[2],
      },
    ],
  },
]

function App() {
  const [conversations, setConversations] = useState<Conversation[]>(initialHistory)
  const [activeId, setActiveId] = useState(initialConversation.id)
  const [prompt, setPrompt] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [traceOpen, setTraceOpen] = useState(
    () => globalThis.matchMedia?.('(min-width: 1280px)').matches ?? true,
  )

  const activeConversation =
    conversations.find((conversation) => conversation.id === activeId) ?? conversations[0]

  const canSubmit = prompt.trim().length > 0 && activeConversation.status !== 'running'

  async function runAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return

    const query = prompt.trim()
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
    }

    const targetId =
      activeConversation.messages.length === 0
        ? activeConversation.id
        : crypto.randomUUID()

    const runningConversation: Conversation = {
      ...emptyConversation(targetId, titleFromPrompt(query)),
      messages: [userMessage],
      subtitle: 'running ReAct loop',
      status: 'running',
    }

    setPrompt('')
    setTraceOpen(true)
    setActiveId(targetId)
    setConversations((current) => upsertConversation(current, runningConversation))

    try {
      const response = await fetch(`${API_BASE_URL}/agent/invoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, stream: false }),
      })

      if (!response.ok) {
        const body = await response.text()
        throw new Error(body || `HTTP ${response.status}`)
      }

      const payload = (await response.json()) as AgentResponse
      const steps = payload.steps?.length ? payload.steps : payload.trace ?? []
      const answer = payload.answer ?? payload.result ?? 'No answer returned.'
      const toolsUsed = payload.tools_used?.length ? payload.tools_used : uniqueTools(steps)
      const latencyMs =
        payload.latency_ms ?? (payload.total_time ? Math.round(payload.total_time * 1000) : null)

      setConversations((current) =>
        upsertConversation(current, {
          ...runningConversation,
          messages: [
            userMessage,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: answer,
              status: 'success',
            },
          ],
          steps,
          toolsUsed,
          latencyMs,
          status: 'success',
          subtitle: toolsUsed.length ? toolsUsed.join(', ') : 'final answer',
          runId: payload.run_id,
        }),
      )
    } catch (error) {
      const content = error instanceof Error ? error.message : 'Unknown API error.'
      setConversations((current) =>
        upsertConversation(current, {
          ...runningConversation,
          messages: [
            userMessage,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content,
              status: 'error',
            },
          ],
          status: 'error',
          subtitle: 'backend request failed',
        }),
      )
    }
  }

  function startNewChat() {
    const id = crypto.randomUUID()
    const conversation = emptyConversation(id, 'New chat')
    setConversations((current) => [conversation, ...current])
    setActiveId(id)
    setPrompt('')
    setSidebarOpen(false)
  }

  return (
    <div className="min-h-screen bg-[#f7f4ee] text-[#201f1c]">
      <div className="flex h-screen overflow-hidden">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={(id) => {
            setActiveId(id)
            setSidebarOpen(false)
          }}
          onNewChat={startNewChat}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          <TopBar
            conversation={activeConversation}
            traceOpen={traceOpen}
            onToggleSidebar={() => setSidebarOpen(true)}
            onToggleTrace={() => setTraceOpen((value) => !value)}
          />

          <div className="flex min-h-0 flex-1">
            <ChatThread conversation={activeConversation} />

            {traceOpen ? (
              <>
                <button
                  type="button"
                  aria-label="Close trace overlay"
                  onClick={() => setTraceOpen(false)}
                  className="fixed inset-0 z-40 bg-black/25 xl:hidden"
                />
                <TraceRail conversation={activeConversation} onClose={() => setTraceOpen(false)} />
              </>
            ) : null}
          </div>

          <Composer
            prompt={prompt}
            setPrompt={setPrompt}
            canSubmit={canSubmit}
            isRunning={activeConversation.status === 'running'}
            onSubmit={runAgent}
          />
        </main>
      </div>
    </div>
  )
}

function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  isOpen,
  onClose,
}: {
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNewChat: () => void
  isOpen: boolean
  onClose: () => void
}) {
  return (
    <>
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[292px] flex-col border-r border-black/10 bg-[#171714] text-[#f7f4ee] transition-transform duration-200 lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#f0dca8] text-[#171714]">
              <Brain className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold">ReAct Agent</p>
              <p className="text-xs text-white/45">Tool-use workspace</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-md text-white/65 hover:bg-white/10 lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={onNewChat}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.07] text-sm font-medium text-white transition hover:bg-white/[0.12]"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>

        <div className="mt-4 px-3">
          <div className="flex h-10 items-center gap-2 rounded-lg bg-black/20 px-3 text-white/45">
            <Search className="h-4 w-4" />
            <span className="text-sm">Search history</span>
          </div>
        </div>

        <div className="mt-4 flex-1 overflow-y-auto px-2 pb-4">
          <p className="px-2 pb-2 text-xs font-medium uppercase tracking-[0.12em] text-white/35">
            History
          </p>
          <div className="space-y-1">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelect(conversation.id)}
                className={`w-full rounded-lg px-3 py-3 text-left transition ${
                  conversation.id === activeId
                    ? 'bg-white/[0.12] text-white'
                    : 'text-white/70 hover:bg-white/[0.07] hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 shrink-0 opacity-65" />
                  <span className="truncate text-sm font-medium">{conversation.title}</span>
                </div>
                <p className="mt-1 truncate pl-6 text-xs text-white/40">{conversation.subtitle}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-white/10 p-3">
          <div className="rounded-lg bg-black/20 p-3">
            <p className="text-xs font-medium text-white/70">Endpoint</p>
            <p className="mt-1 truncate font-mono text-xs text-white/40">{API_BASE_URL}/agent/invoke</p>
          </div>
        </div>
      </aside>

      {isOpen ? (
        <button
          type="button"
          aria-label="Close sidebar overlay"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
        />
      ) : null}
    </>
  )
}

function TopBar({
  conversation,
  traceOpen,
  onToggleSidebar,
  onToggleTrace,
}: {
  conversation: Conversation
  traceOpen: boolean
  onToggleSidebar: () => void
  onToggleTrace: () => void
}) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-[#fbfaf7]/85 px-3 backdrop-blur md:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="grid h-9 w-9 place-items-center rounded-lg text-[#6d675c] hover:bg-black/[0.05] lg:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold md:text-lg">ReAct Agent with Tool Use</h1>
          <p className="truncate text-xs text-[#7d776b]">{conversation.title}</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <StatusPill status={conversation.status} />
        <button
          type="button"
          onClick={onToggleTrace}
          className={`inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-sm transition ${
            traceOpen
              ? 'border-[#cdbb8c] bg-[#fff4d8] text-[#4a3b16]'
              : 'border-black/10 bg-white text-[#5d574c] hover:bg-black/[0.04]'
          }`}
        >
          <PanelRight className="h-4 w-4" />
          <span className="hidden sm:inline">Trace</span>
        </button>
      </div>
    </header>
  )
}

function ChatThread({ conversation }: { conversation: Conversation }) {
  const hasMessages = conversation.messages.length > 0

  return (
    <section className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-7 md:px-6">
        {!hasMessages ? <EmptyState /> : null}

        <div className="space-y-6">
          {conversation.messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
          {conversation.status === 'running' ? <ThinkingMessage /> : null}
        </div>
      </div>
    </section>
  )
}

function EmptyState() {
  return (
    <div className="m-auto w-full max-w-2xl text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#211f1b] text-[#f0dca8]">
        <Sparkles className="h-5 w-5" />
      </div>
      <h2 className="mt-5 text-2xl font-semibold tracking-tight">Ask the agent to reason with tools.</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[#7d776b]">
        Use a prompt that benefits from search, calculation, or Python execution. The trace stays available without turning the chat into a systems diagram.
      </p>
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <article className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser ? (
        <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#211f1b] text-[#f0dca8]">
          <Brain className="h-4 w-4" />
        </div>
      ) : null}

      <div className={`max-w-[84%] ${isUser ? 'order-first' : ''}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${
            isUser
              ? 'rounded-br-md bg-[#211f1b] text-white'
              : message.status === 'error'
                ? 'rounded-bl-md border border-[#e7b8aa] bg-[#fff2ef] text-[#6f2517]'
                : 'rounded-bl-md border border-black/10 bg-white text-[#27241f]'
          }`}
        >
          {message.content}
        </div>
        {!isUser && message.status ? (
          <div className="mt-2 flex items-center gap-2 pl-1 text-xs text-[#8a8377]">
            {message.status === 'error' ? (
              <AlertTriangle className="h-3.5 w-3.5 text-[#bd5039]" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 text-[#3b7f5b]" />
            )}
            <span>{message.status === 'preview' ? 'preview trace' : message.status}</span>
          </div>
        ) : null}
      </div>
    </article>
  )
}

function ThinkingMessage() {
  return (
    <article className="flex gap-3">
      <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#211f1b] text-[#f0dca8]">
        <Brain className="h-4 w-4" />
      </div>
      <div className="rounded-2xl rounded-bl-md border border-black/10 bg-white px-4 py-3 text-sm text-[#5d574c] shadow-sm">
        <span className="inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Running ReAct loop
        </span>
      </div>
    </article>
  )
}

function Composer({
  prompt,
  setPrompt,
  canSubmit,
  isRunning,
  onSubmit,
}: {
  prompt: string
  setPrompt: (value: string) => void
  canSubmit: boolean
  isRunning: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <footer className="shrink-0 border-t border-black/10 bg-[#fbfaf7]/90 px-4 py-4 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {quickPrompts.map((quickPrompt) => (
            <button
              key={quickPrompt}
              type="button"
              onClick={() => setPrompt(quickPrompt)}
              className="shrink-0 rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-[#5d574c] shadow-sm transition hover:border-[#cdbb8c] hover:bg-[#fff7e3]"
            >
              {quickLabel(quickPrompt)}
            </button>
          ))}
        </div>

        <form
          onSubmit={onSubmit}
          className="flex items-end gap-2 rounded-2xl border border-black/10 bg-white p-2 shadow-[0_16px_40px_rgba(32,31,28,0.12)]"
        >
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder="Message the ReAct agent..."
            className="max-h-36 min-h-12 flex-1 resize-none rounded-xl bg-transparent px-3 py-3 text-sm leading-6 text-[#27241f] outline-none placeholder:text-[#aaa295]"
          />
          <button
            type="submit"
            disabled={!canSubmit}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#211f1b] text-white transition hover:bg-black disabled:cursor-not-allowed disabled:bg-[#d7d0c4]"
            aria-label="Send message"
          >
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </div>
    </footer>
  )
}

function TraceRail({
  conversation,
  onClose,
}: {
  conversation: Conversation
  onClose: () => void
}) {
  const hasTrace = conversation.steps.length > 0
  const finalAnswer = lastAssistantMessage(conversation)?.content

  return (
    <aside className="fixed inset-y-0 right-0 z-50 flex w-[min(92vw,352px)] shrink-0 flex-col border-l border-black/10 bg-[#f0ece3] shadow-2xl xl:static xl:z-auto xl:w-[352px] xl:shadow-none">
      <div className="flex h-16 items-center justify-between border-b border-black/10 px-4">
        <div>
          <p className="text-sm font-semibold">ReAct trace</p>
          <p className="text-xs text-[#7d776b]">quiet instrumentation</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="grid h-8 w-8 place-items-center rounded-md text-[#6d675c] hover:bg-black/[0.05]"
          aria-label="Close trace"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-4 overflow-y-auto p-4">
        <TraceMetrics conversation={conversation} />

        {!hasTrace ? (
          <div className="rounded-xl border border-dashed border-black/15 bg-white/60 p-4 text-sm leading-6 text-[#7d776b]">
            No tool calls yet. Run a prompt to populate the timeline.
          </div>
        ) : (
          <div className="space-y-3">
            {conversation.steps.map((step, index) => (
              <TraceStep key={`${step.action}-${index}`} step={step} index={index + 1} />
            ))}
          </div>
        )}

        {finalAnswer ? (
          <div className="rounded-xl border border-black/10 bg-[#211f1b] p-4 text-white">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-white/45">Final answer</p>
            <p className="mt-3 text-sm leading-6 text-white/82">{finalAnswer}</p>
          </div>
        ) : null}
      </div>
    </aside>
  )
}

function TraceMetrics({ conversation }: { conversation: Conversation }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <Metric
        icon={Wrench}
        label="Tools"
        value={conversation.toolsUsed.length ? conversation.toolsUsed.length.toString() : '0'}
      />
      <Metric icon={Timer} label="Latency" value={conversation.latencyMs ? `${conversation.latencyMs}ms` : '-'} />
      <Metric icon={Activity} label="Status" value={conversation.status} />
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-black/10 bg-white/70 p-3">
      <Icon className="h-4 w-4 text-[#6f5a21]" />
      <p className="mt-2 text-[10px] font-medium uppercase tracking-[0.12em] text-[#8a8377]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[#27241f]" title={value}>
        {value}
      </p>
    </div>
  )
}

function TraceStep({ step, index }: { step: Step; index: number }) {
  return (
    <div className="rounded-xl border border-black/10 bg-white/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <ToolIcon action={step.action} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[#27241f]">{step.action}</p>
            <p className="text-xs text-[#8a8377]">step {index}</p>
          </div>
        </div>
        <span className="rounded-full bg-[#edf7ef] px-2 py-1 text-xs text-[#3b7f5b]">ok</span>
      </div>

      <TraceLine label="Thought" value={step.thought} />
      <TraceLine label="Input" value={step.action_input} mono />
      <TraceLine label="Observation" value={step.observation} />
    </div>
  )
}

function TraceLine({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="mt-3 border-t border-black/10 pt-3">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#8a8377]">{label}</p>
      <p className={`mt-1 line-clamp-3 text-xs leading-5 text-[#5d574c] ${mono ? 'font-mono' : ''}`}>
        {value || '-'}
      </p>
    </div>
  )
}

function ToolIcon({ action }: { action: string }) {
  const className = 'h-4 w-4'
  if (action.includes('calculator')) return <Calculator className={className} />
  if (action.includes('python')) return <Terminal className={className} />
  if (action.includes('search')) return <Search className={className} />
  if (action.includes('final')) return <CheckCircle2 className={className} />
  return <Code2 className={className} />
}

function StatusPill({ status }: { status: Conversation['status'] }) {
  const label = status === 'idle' ? 'ready' : status
  const classes = {
    idle: 'bg-[#ece8df] text-[#5d574c]',
    running: 'bg-[#fff4d8] text-[#6f5a21]',
    success: 'bg-[#edf7ef] text-[#3b7f5b]',
    error: 'bg-[#fff2ef] text-[#bd5039]',
  }

  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${classes[status]}`}>
      {label}
    </span>
  )
}

function emptyConversation(id: string, title: string): Conversation {
  return {
    id,
    title,
    subtitle: 'No trace yet',
    messages: [],
    steps: [],
    toolsUsed: [],
    latencyMs: null,
    status: 'idle',
  }
}

function upsertConversation(current: Conversation[], next: Conversation) {
  const filtered = current.filter((conversation) => conversation.id !== next.id)
  return [next, ...filtered]
}

function titleFromPrompt(prompt: string) {
  const cleaned = prompt.replace(/\s+/g, ' ').trim()
  return cleaned.length > 42 ? `${cleaned.slice(0, 42)}...` : cleaned || 'New chat'
}

function quickLabel(prompt: string) {
  if (prompt.startsWith('Search')) return 'Latest AI trends'
  if (prompt.startsWith('Calculate')) return 'Compound growth'
  return 'Python statistics'
}

function uniqueTools(steps: Step[]) {
  return Array.from(
    new Set(
      steps
        .map((step) => step.action)
        .filter((action) => action && action !== 'final'),
    ),
  )
}

function lastAssistantMessage(conversation: Conversation) {
  return [...conversation.messages].reverse().find((message) => message.role === 'assistant')
}

export default App
