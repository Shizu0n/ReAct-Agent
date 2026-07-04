import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent, KeyboardEvent } from 'react'
import { CornerDownLeft, FileText, LoaderIcon, Paperclip, SendIcon, Trash2, X } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { DocumentInfo } from '../../types'
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
  documents?: DocumentInfo[]
  uploading?: boolean
  uploadError?: string | null
  onUploadFile?: (file: File) => void
  onDeleteDocument?: (docId: string) => void
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
  documents = [],
  uploading = false,
  uploadError = null,
  onUploadFile,
  onDeleteDocument,
}: AnimatedAIChatProps) {
  const [inputFocused, setInputFocused] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 40, maxHeight: 150 })
  const canSend = value.trim().length > 0 && !disabled && !isLoading

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) onUploadFile?.(file)
  }

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
        {documents.length > 0 || uploading ? (
          <div className="flex flex-wrap items-center gap-1.5 border-b border-white/[0.06] px-4 py-2">
            {documents.map((doc) => (
              <span
                key={doc.id}
                title={`${doc.filename} · ${doc.chunk_count} chunk${doc.chunk_count === 1 ? '' : 's'}`}
                className="group inline-flex max-w-[14rem] items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono text-[0.62rem] text-[var(--text-secondary)]"
              >
                <FileText className="h-3 w-3 shrink-0 text-[var(--accent-text)]" />
                <span className="truncate">{doc.filename}</span>
                <span className="shrink-0 text-[var(--text-tertiary)]">{doc.chunk_count}</span>
                {onDeleteDocument ? (
                  <button
                    type="button"
                    onClick={() => onDeleteDocument(doc.id)}
                    title={`Remove ${doc.filename}`}
                    aria-label={`Remove ${doc.filename}`}
                    className="-mr-1 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                ) : null}
              </span>
            ))}
            {uploading ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-2.5 py-1 font-mono text-[0.62rem] text-[var(--text-secondary)]">
                <LoaderIcon className="h-3 w-3 animate-spin text-[var(--accent-text)]" />
                Ingesting…
              </span>
            ) : null}
          </div>
        ) : null}
        {uploadError ? (
          <p className="border-b border-[var(--error)]/20 px-4 py-1.5 text-xs text-red-400">{uploadError}</p>
        ) : null}

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
            <CornerDownLeft className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="font-mono uppercase tracking-[0.12em] sm:hidden">Enter sends</span>
            <span className="hidden truncate font-mono uppercase tracking-[0.12em] sm:inline">Enter sends · Shift Enter breaks line</span>
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            {onUploadFile ? (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,application/pdf,text/plain"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  title="Upload document (PDF, TXT, MD · max 2 MB)"
                  className="grid h-10 w-10 place-items-center rounded-lg border border-transparent text-[var(--text-tertiary)] transition-colors hover:border-[var(--border-subtle)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-35"
                  aria-label="Upload document"
                >
                  {uploading ? <LoaderIcon className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
                </button>
              </>
            ) : null}

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
