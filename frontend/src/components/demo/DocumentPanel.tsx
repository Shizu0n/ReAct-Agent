import { useRef, useState, type ChangeEvent } from 'react'
import { FileText, Upload } from 'lucide-react'
import type { UploadResult } from '../../types'
import { useDocuments } from '../../hooks/useDocuments'

type DocumentPanelProps = {
  sessionId: string
}

export function DocumentPanel({ sessionId }: DocumentPanelProps) {
  const { documents, uploading, error, uploadDocument } = useDocuments(sessionId)
  const inputRef = useRef<HTMLInputElement>(null)
  const [lastResult, setLastResult] = useState<UploadResult | null>(null)

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const result = await uploadDocument(file)
    if (result) setLastResult(result)
  }

  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-4 py-3 lg:px-8">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Upload className="h-4 w-4" />
          {uploading ? 'Ingesting...' : 'Upload document'}
        </button>
        {lastResult && !uploading ? (
          <span className="font-mono text-[0.7rem] text-[var(--text-tertiary)]">
            Stored {lastResult.chunks_stored} chunk{lastResult.chunks_stored === 1 ? '' : 's'}
            {lastResult.status === 'truncated' ? ` (${lastResult.chunks_skipped} skipped)` : ''}
          </span>
        ) : null}
      </div>

      {error ? <p className="mt-2 text-sm text-red-400">{error}</p> : null}

      <ul className="mt-3 space-y-1">
        {documents.length === 0 ? (
          <li className="font-mono text-[0.7rem] text-[var(--text-tertiary)]">
            No documents uploaded yet.
          </li>
        ) : (
          documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center gap-2 font-mono text-[0.7rem] text-[var(--text-secondary)]"
            >
              <FileText className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />
              <span className="truncate">{doc.filename}</span>
              <span className="text-[var(--text-tertiary)]">
                {doc.chunk_count} chunk{doc.chunk_count === 1 ? '' : 's'}
              </span>
            </li>
          ))
        )}
      </ul>
    </div>
  )
}
