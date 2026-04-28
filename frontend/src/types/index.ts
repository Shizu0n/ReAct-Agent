export type StepType = 'thought' | 'action' | 'observation' | 'final'

export interface Step {
  type?: StepType
  content?: string
  step: number
  tool?: string
  thought?: string
  action?: string | null
  action_input?: string
  observation?: string
  run_id?: string
  elapsed_ms?: number
  tools_used?: string[]
  status?: 'running' | 'success' | 'error'
  timestamp: string
}

export type StreamEvent = {
  type: StepType
  content: string
  step: number
  tool?: string
  action_input?: string
  run_id?: string
  timestamp?: string
  elapsed_ms?: number
  tools_used?: string[]
  status?: 'running' | 'success' | 'error'
}

export interface AgentResponse {
  result: string
  trace: Step[]
  total_time: number
  run_id: string
  answer: string
  steps: Step[]
  tools_used: string[]
  latency_ms: number
  status: 'success' | 'error'
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface RunSummary {
  run_id?: string
  elapsed_ms?: number
  tools_used: string[]
  status?: 'running' | 'success' | 'error'
}

export interface AgentState {
  messages: Message[]
  steps: Step[]
  isLoading: boolean
  error: string | null
  config: AgentConfig | null
  runSummary: RunSummary | null
  connectionStatus: 'checking' | 'online' | 'mock' | 'error'
}

export interface ModelInfo {
  provider: string
  provider_label: string
  model: string
  label: string
}

export interface AgentConfig {
  status: 'configured' | 'unconfigured'
  active_model: ModelInfo | null
  fallback_models: ModelInfo[]
  tools: string[]
}
