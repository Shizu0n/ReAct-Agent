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
}
