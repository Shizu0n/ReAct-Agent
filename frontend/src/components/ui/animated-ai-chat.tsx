import { useCallback, useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Command, LoaderIcon, SendIcon, Trash2 } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { ProjectMark } from '../ProjectMark'

type AnimatedAIChatProps = {
  value: string
  onValueChange: (value: string) => void
  onSubmit: (value: string) => void
  disabled?: boolean
  isLoading?: boolean
  onClearHistory?: () => void
  canClearHistory?: boolean
  placeholder?: string
}

type UseAutoResizeTextareaProps = {
  minHeight: number
  maxHeight?: number
}

function useAutoResizeTextarea({ minHeight, maxHeight }: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current
      if (!textarea) return

      textarea.style.height = `${minHeight}px`
      if (reset) return

      const newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY))
      textarea.style.height = `${newHeight}px`
    },
    [maxHeight, minHeight],
  )

  useEffect(() => {
    adjustHeight()
  }, [adjustHeight])

  return { textareaRef, adjustHeight }
}

export function AnimatedAIChat({
  value,
  onValueChange,
  onSubmit,
  disabled = false,
  isLoading = false,
  onClearHistory,
  canClearHistory = false,
  placeholder = 'Message the ReAct agent...',
}: AnimatedAIChatProps) {
  const [inputFocused, setInputFocused] = useState(false)
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 40, maxHeight: 150 })
  const canSend = value.trim().length > 0 && !disabled && !isLoading

  useEffect(() => {
    if (value.length === 0) {
      adjustHeight(true)
    }
  }, [adjustHeight, value.length])

  function submit(): void {
    if (!canSend) return
    onSubmit(value)
    adjustHeight(true)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="relative min-w-0 max-w-[100vw] bg-[var(--bg-primary)] px-3 pb-3 pt-1 sm:px-4 sm:pb-4 sm:pt-1 lg:px-8"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <motion.div
        className={cn(
          'relative min-w-0 overflow-hidden rounded-2xl border bg-[var(--bg-secondary)] shadow-[0_24px_80px_rgba(0,0,0,0.22)]',
          inputFocused ? 'border-[var(--accent-border)] shadow-[0_24px_80px_rgba(214,255,127,0.08)]' : 'border-white/[0.07]',
        )}
        initial={{ scale: 0.985, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
      >
        <div className="flex items-start gap-3 px-4 py-2">
          <div className="mt-1 hidden h-7 w-7 flex-shrink-0 place-items-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--accent-text)] sm:grid">
            <ProjectMark className="h-3.5 w-3.5" />
          </div>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => {
              onValueChange(event.target.value)
              adjustHeight()
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            disabled={disabled || isLoading}
            placeholder={placeholder}
            className="min-h-10 min-w-0 flex-1 resize-none overflow-hidden bg-transparent px-0 py-2 text-[0.95rem] leading-6 text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-white/[0.06] px-4 py-2">
          <div className="flex min-w-0 items-center gap-2 text-[0.68rem] text-[var(--text-tertiary)]">
            <Command className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="font-mono uppercase tracking-[0.12em] sm:hidden">Enter sends</span>
            <span className="hidden truncate font-mono uppercase tracking-[0.12em] sm:inline">Enter sends · Shift Enter breaks line</span>
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            {onClearHistory ? (
              <button
                type="button"
                onClick={onClearHistory}
                disabled={!canClearHistory || isLoading}
                title="Clear chat history"
                className="grid h-10 w-10 place-items-center rounded-lg border border-transparent text-[var(--text-tertiary)] transition-colors hover:border-[var(--border-subtle)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-35"
                aria-label="Clear chat history"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}

            <motion.button
              type="submit"
              whileHover={canSend ? { scale: 1.01 } : undefined}
              whileTap={canSend ? { scale: 0.98 } : undefined}
              disabled={!canSend}
              className={cn(
                'inline-flex h-10 min-w-10 flex-shrink-0 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium transition-colors',
                canSend
                  ? 'bg-[var(--accent-text)] text-[var(--bg-primary)] hover:bg-[var(--accent)]'
                  : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]',
              )}
              aria-label="Send message"
            >
              {isLoading ? <LoaderIcon className="h-4 w-4 animate-spin" /> : <SendIcon className="h-4 w-4" />}
              <span className="hidden sm:inline">Send</span>
            </motion.button>
          </div>
        </div>
      </motion.div>

    </form>
  )
}
