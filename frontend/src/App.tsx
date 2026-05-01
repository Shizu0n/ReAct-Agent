import { useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import { Code2, ExternalLink, Info, Menu, X } from 'lucide-react'
import { ChatWorkspace } from './components/ChatWorkspace'
import { PortfolioView } from './components/PortfolioView'
import { ProjectMark } from './components/ProjectMark'
import { useAgent } from './hooks/useAgent'

const LEFT_SIDEBAR_MIN = 220
const LEFT_SIDEBAR_MAX = 420
const LEFT_SIDEBAR_DEFAULT = 288
const RIGHT_SIDEBAR_DEFAULT = 400

const navItems = [
  { id: 'chat', label: 'Chat', icon: ProjectMark },
  { id: 'portfolio', label: 'About', icon: Info },
] as const

type ActiveTab = (typeof navItems)[number]['id']
type TraceOpenUpdate = boolean | ((current: boolean) => boolean)
type PersistedShellState = {
  sidebarHidden: boolean
  traceOpen: boolean
  traceAutoOpened: boolean
  traceDismissed: boolean
}

const shellStorageKey = 'react-agent:shell-state:v1'
const defaultShellState: PersistedShellState = {
  sidebarHidden: false,
  traceOpen: false,
  traceAutoOpened: false,
  traceDismissed: false,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function readShellState(): PersistedShellState {
  if (typeof window === 'undefined') return defaultShellState

  try {
    const rawState = window.localStorage.getItem(shellStorageKey)
    if (!rawState) return defaultShellState

    const parsed = JSON.parse(rawState) as unknown
    if (!isRecord(parsed)) return defaultShellState

    return {
      sidebarHidden: typeof parsed.sidebarHidden === 'boolean' ? parsed.sidebarHidden : defaultShellState.sidebarHidden,
      traceOpen: typeof parsed.traceOpen === 'boolean' ? parsed.traceOpen : defaultShellState.traceOpen,
      traceAutoOpened: typeof parsed.traceAutoOpened === 'boolean' ? parsed.traceAutoOpened : defaultShellState.traceAutoOpened,
      traceDismissed: typeof parsed.traceDismissed === 'boolean' ? parsed.traceDismissed : defaultShellState.traceDismissed,
    }
  } catch {
    window.localStorage.removeItem(shellStorageKey)
    return defaultShellState
  }
}

function writeShellState(patch: Partial<PersistedShellState>): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(shellStorageKey, JSON.stringify({ ...readShellState(), ...patch }))
}

function App() {
  const { state, sendQuery, clearHistory } = useAgent()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarHidden, setSidebarHidden] = useState(() => readShellState().sidebarHidden)
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(LEFT_SIDEBAR_DEFAULT)
  const [traceOpen, setTraceOpen] = useState(() => readShellState().traceOpen)
  const [rightSidebarWidth, setRightSidebarWidth] = useState(RIGHT_SIDEBAR_DEFAULT)
  const [mobileTraceOpen, setMobileTraceOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<ActiveTab>('chat')

  function switchTab(tab: ActiveTab): void {
    setActiveTab(tab)
    setSidebarOpen(false)
  }

  function handleTraceOpenChange(open: TraceOpenUpdate): void {
    setTraceOpen((current) => {
      const nextOpen = typeof open === 'function' ? open(current) : open
      writeShellState({ traceOpen: nextOpen })
      return nextOpen
    })
  }

  function handleMobileTraceOpenChange(open: boolean): void {
    writeShellState({ traceOpen: open })
    setTraceOpen(open)
    setMobileTraceOpen(open)
  }

  function handleReasoningStart(): void {
    writeShellState({ traceOpen })
  }

  function toggleDesktopSidebar(): void {
    setSidebarHidden((current) => {
      const nextHidden = !current
      writeShellState({ sidebarHidden: nextHidden })
      return nextHidden
    })
  }

  function startLeftResize(event: ReactPointerEvent<HTMLDivElement>): void {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = leftSidebarWidth

    function handlePointerMove(moveEvent: PointerEvent): void {
      const nextWidth = startWidth + moveEvent.clientX - startX
      setLeftSidebarWidth(Math.min(LEFT_SIDEBAR_MAX, Math.max(LEFT_SIDEBAR_MIN, nextWidth)))
    }

    function stopResize(): void {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResize)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResize)
  }

  return (
    <div className="relative min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <button
        type="button"
        onClick={() => {
          if (window.matchMedia('(min-width: 1024px)').matches) {
            toggleDesktopSidebar()
            return
          }
          setSidebarOpen((current) => !current)
        }}
        className={`fixed top-4 z-50 flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] shadow-lg transition-[left,background-color,color,border-color] duration-300 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] ${
          sidebarHidden ? 'left-4' : 'left-4 lg:left-[var(--left-sidebar-toggle)]'
        }`}
        style={{ '--left-sidebar-toggle': `${leftSidebarWidth - 60}px` } as CSSProperties}
        aria-label="Toggle sidebar"
      >
        <span className="lg:hidden">
          {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </span>
        <span className="hidden lg:block">
          {sidebarHidden ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
        </span>
      </button>

      <aside
        className={`fixed left-0 top-0 z-40 flex h-full w-72 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4 transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } ${sidebarHidden ? 'lg:-translate-x-full' : 'lg:translate-x-0'
        }`}
        style={{ width: leftSidebarWidth }}
      >
        <div className="mb-8 mt-12 flex items-center gap-3 px-2 lg:mt-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-default)] bg-[var(--bg-tertiary)]">
            <ProjectMark className="h-[18px] w-[18px] text-[var(--accent-text)]" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">ReAct Agent</p>
            <p className="text-xs text-[var(--text-tertiary)]">Chat-first ML demo</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => switchTab(item.id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                activeTab === item.id
                  ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)] ring-1 ring-[var(--border-default)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>

        <a
          href="https://github.com/Shizu0n/react-agent"
          target="_blank"
          rel="noreferrer"
          className="mt-auto flex items-center gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-secondary)] transition hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
        >
          <Code2 className="h-4 w-4" />
          Source code
          <ExternalLink className="ml-auto h-3.5 w-3.5" />
        </a>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize left sidebar"
          className="absolute right-0 top-0 hidden h-full w-2 translate-x-1 cursor-col-resize touch-none lg:block"
          onPointerDown={startLeftResize}
        >
          <span className="mx-auto block h-full w-px bg-transparent transition-colors hover:bg-[var(--accent-border)]" />
        </div>
      </aside>

      <main
        className={`min-h-screen transition-[margin] duration-300 ${sidebarHidden ? 'lg:ml-0' : 'lg:ml-[var(--left-sidebar-width)]'}`}
        style={{ '--left-sidebar-width': `${leftSidebarWidth}px` } as CSSProperties}
      >
        {activeTab === 'chat' ? (
          <ChatWorkspace
            state={state}
            sendQuery={sendQuery}
            clearHistory={clearHistory}
            sidebarHidden={sidebarHidden}
            traceOpen={traceOpen}
            rightSidebarWidth={rightSidebarWidth}
            mobileTraceOpen={mobileTraceOpen}
            onTraceOpenChange={handleTraceOpenChange}
            onRightSidebarWidthChange={setRightSidebarWidth}
            onMobileTraceOpenChange={handleMobileTraceOpenChange}
            onReasoningStart={handleReasoningStart}
            onOpenPortfolio={() => switchTab('portfolio')}
          />
        ) : (
          <PortfolioView onOpenChat={() => switchTab('chat')} />
        )}
      </main>
    </div>
  )
}

export default App
