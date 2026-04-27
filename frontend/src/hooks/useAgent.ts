import { useEffect, useState } from 'react'
import type { AgentConfig, AgentState, Message, Step, StepType } from '../types'

type StreamPayload = {
  type: StepType
  content: string
  step: number
  tool?: string
}

type SseParseResult = {
  events: string[]
  remainder: string
}

type ApiHistoryMessage = Pick<Message, 'role' | 'content'>

const initialState: AgentState = {
  messages: [],
  steps: [],
  isLoading: false,
  error: null,
  config: null,
  connectionStatus: 'checking',
}

const mockSteps: Array<Omit<Step, 'timestamp'>> = [
  {
    type: 'thought',
    content: 'I need to look up information to answer this accurately.',
    step: 1,
  },
  {
    type: 'action',
    content: 'Searching for relevant information.',
    step: 2,
    tool: 'web_search',
  },
  {
    type: 'observation',
    content: 'Found relevant results. Analyzing content.',
    step: 3,
  },
  {
    type: 'thought',
    content: 'I have enough information to provide a complete answer.',
    step: 4,
  },
  {
    type: 'final',
    content: 'Demo fallback enabled via VITE_AGENT_MOCK.',
    step: 5,
  },
]

function timestamp(): string {
  return new Date().toISOString()
}

function withTimestamp(step: Omit<Step, 'timestamp'>): Step {
  return { ...step, timestamp: timestamp() }
}

function apiBaseUrl(): string {
  const configuredUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '')
  }

  return '/api'
}

function shouldUseMockFallback(): boolean {
  return (import.meta.env.VITE_AGENT_MOCK as string | undefined) === 'true'
}

function historyForApi(messages: Message[]): ApiHistoryMessage[] {
  return messages
    .filter((message) => message.content.trim().length > 0)
    .slice(-8)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }))
}

function makeUserMessage(query: string): Message {
  return {
    id: crypto.randomUUID(),
    role: 'user',
    content: query,
  }
}

function makeAssistantMessage(id: string): Message {
  return {
    id,
    role: 'assistant',
    content: '',
  }
}

function parseSseEvents(buffer: string): SseParseResult {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  return {
    events: parts.slice(0, -1),
    remainder: parts[parts.length - 1] ?? '',
  }
}

function sseDataFromEvent(eventBlock: string): string | null {
  const data = eventBlock
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')

  return data.length > 0 ? data : null
}

async function requestErrorMessage(response: Response): Promise<string> {
  const fallback = `Agent request failed with HTTP ${response.status}`

  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? `${fallback}: ${body.detail}` : fallback
  } catch {
    return fallback
  }
}

export function useAgent() {
  const [state, setState] = useState<AgentState>(initialState)

  useEffect(() => {
    let cancelled = false

    async function loadConfig(): Promise<void> {
      if (shouldUseMockFallback()) {
        setState((current) => ({
          ...current,
          config: null,
          connectionStatus: 'mock',
        }))
        return
      }

      try {
        const response = await fetch(`${apiBaseUrl()}/config`, {
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) {
          throw new Error(await requestErrorMessage(response))
        }

        const config = (await response.json()) as AgentConfig
        if (cancelled) return

        setState((current) => ({
          ...current,
          config,
          connectionStatus: 'online',
        }))
      } catch (error) {
        if (cancelled) return

        setState((current) => ({
          ...current,
          config: null,
          error: error instanceof Error ? error.message : 'Unable to reach the FastAPI backend.',
          connectionStatus: 'error',
        }))
      }
    }

    void loadConfig()

    return () => {
      cancelled = true
    }
  }, [])

  function updateAssistantMessage(assistantId: string, content: string): void {
    setState((current) => ({
      ...current,
      messages: current.messages.map((message) =>
        message.id === assistantId ? { ...message, content } : message,
      ),
    }))
  }

  async function runMock(assistantId: string): Promise<void> {
    await new Promise((resolve) => window.setTimeout(resolve, 600))

    for (const step of mockSteps) {
      const stampedStep = withTimestamp(step)
      setState((current) => ({
        ...current,
        steps: [...current.steps, stampedStep],
      }))

      if (stampedStep.type === 'final') {
        updateAssistantMessage(assistantId, stampedStep.content)
      }

      await new Promise((resolve) => window.setTimeout(resolve, 900))
    }

    setState((current) => ({ ...current, isLoading: false, connectionStatus: 'mock' }))
  }

  function applyStreamPayload(payload: StreamPayload, assistantId: string): boolean {
    const step = withTimestamp(payload)

    setState((current) => ({
      ...current,
      steps: [...current.steps, step],
    }))

    if (step.type !== 'final') {
      return false
    }

    updateAssistantMessage(assistantId, step.content)
    setState((current) => ({ ...current, isLoading: false, connectionStatus: 'online' }))
    return true
  }

  async function runApi(
    query: string,
    assistantId: string,
    history: Message[],
  ): Promise<void> {
    if (shouldUseMockFallback()) {
      await runMock(assistantId)
      return
    }

    const baseUrl = apiBaseUrl()
    let receivedEvent = false
    let completed = false

    try {
      const response = await fetch(`${baseUrl}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, stream: true, history: historyForApi(history) }),
      })

      if (!response.ok || !response.body) {
        throw new Error(await requestErrorMessage(response))
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (!completed) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parsed = parseSseEvents(buffer)
        buffer = parsed.remainder

        for (const eventBlock of parsed.events) {
          const data = sseDataFromEvent(eventBlock)
          if (!data) continue

          receivedEvent = true
          completed = applyStreamPayload(JSON.parse(data) as StreamPayload, assistantId)
          if (completed) {
            await reader.cancel()
            break
          }
        }
      }

      buffer += decoder.decode()
      const trailingData = sseDataFromEvent(buffer)
      if (!completed && trailingData) {
        receivedEvent = true
        completed = applyStreamPayload(JSON.parse(trailingData) as StreamPayload, assistantId)
      }

      if (!completed) {
        throw new Error('The agent stream closed before returning a final answer.')
      }
    } catch (error) {
      if (!receivedEvent && !completed && shouldUseMockFallback()) {
        await runMock(assistantId)
        return
      }

      setState((current) => ({
        ...current,
        isLoading: false,
        error: error instanceof Error ? error.message : 'The agent stream failed.',
        connectionStatus: 'error',
      }))
    }
  }

  function sendQuery(query: string): void {
    const trimmedQuery = query.trim()
    if (!trimmedQuery || state.isLoading) return

    const assistantId = crypto.randomUUID()
    const userMessage = makeUserMessage(trimmedQuery)
    const assistantMessage = makeAssistantMessage(assistantId)

    setState((current) => ({
      ...current,
      messages: [...current.messages, userMessage, assistantMessage],
      steps: [],
      isLoading: true,
      error: null,
    }))

    void runApi(trimmedQuery, assistantId, state.messages)
  }

  return { state, sendQuery }
}
