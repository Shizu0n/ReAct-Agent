export type StepType = 'thought' | 'action' | 'observation' | 'final'

export interface Usage {
  llm_calls: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  estimated_cost_usd: number
  providers: string[]
}

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
  usage?: Usage
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
  usage?: Usage
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
  usage?: Usage
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
  usage?: Usage
}

export interface AgentState {
  messages: Message[]
  steps: Step[]
  isLoading: boolean
  error: string | null
  config: AgentConfig | null
  runSummary: RunSummary | null
  connectionStatus: 'checking' | 'online' | 'mock' | 'error'
  suggestions: string[]
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
