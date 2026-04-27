export type StepType = 'thought' | 'action' | 'observation' | 'final'

export interface Step {
  type: StepType
  content: string
  step: number
  tool?: string
  timestamp: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface AgentState {
  messages: Message[]
  steps: Step[]
  isLoading: boolean
  error: string | null
  config: AgentConfig | null
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
