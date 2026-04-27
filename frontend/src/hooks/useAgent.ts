import { useState } from 'react'
import type { AgentState, Message, Step, StepType } from '../types'

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

const initialState: AgentState = {
  messages: [],
  steps: [],
  isLoading: false,
  error: null,
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
    content: 'This is a mock response. Connect the FastAPI backend to see real agent reasoning.',
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
  return (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
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

export function useAgent() {
  const [state, setState] = useState<AgentState>(initialState)

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

    setState((current) => ({ ...current, isLoading: false }))
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
    setState((current) => ({ ...current, isLoading: false }))
    return true
  }

  async function runApi(query: string, assistantId: string): Promise<void> {
    const baseUrl = apiBaseUrl()
    if (!baseUrl) {
      await runMock(assistantId)
      return
    }

    let receivedEvent = false
    let completed = false

    try {
      const response = await fetch(`${baseUrl}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, stream: true }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`Agent request failed with HTTP ${response.status}`)
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
      if (!receivedEvent && !completed) {
        await runMock(assistantId)
        return
      }

      setState((current) => ({
        ...current,
        isLoading: false,
        error: error instanceof Error ? error.message : 'The agent stream failed.',
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

    void runApi(trimmedQuery, assistantId)
  }

  return { state, sendQuery }
}
