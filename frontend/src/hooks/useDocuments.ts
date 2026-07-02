import { useCallback, useEffect, useState } from 'react'
import type { DocumentInfo, UploadResult } from '../types'

// Local copy of useAgent's apiBaseUrl (the private one there is not exported).
function apiBaseUrl(): string {
  const configuredUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '')
  }
  return '/api'
}

// Reuses the session id created by useAgent (localStorage react-agent:session-id),
// passed in as a prop — this hook never creates a second session id.
export function useDocuments(sessionId: string) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const listDocuments = useCallback(async (): Promise<void> => {
    if (!sessionId) return
    try {
      const response = await fetch(`${apiBaseUrl()}/documents/${sessionId}`, {
        headers: { 'x-session-id': sessionId },
      })
      if (!response.ok) {
        setDocuments([])
        return
      }
      const data = (await response.json()) as { documents?: DocumentInfo[] }
      setDocuments(Array.isArray(data.documents) ? data.documents : [])
    } catch {
      setDocuments([])
    }
  }, [sessionId])

  const uploadDocument = useCallback(
    async (file: File): Promise<UploadResult | null> => {
      if (uploading) return null
      setUploading(true)
      setError(null)
      try {
        const form = new FormData()
        form.append('file', file)
        // Do not set Content-Type: the browser adds the multipart boundary.
        const response = await fetch(`${apiBaseUrl()}/upload`, {
          method: 'POST',
          headers: { 'x-session-id': sessionId },
          body: form,
        })
        if (!response.ok) {
          let detail = `Upload failed (${response.status})`
          try {
            const body = (await response.json()) as { detail?: string }
            if (body.detail) detail = body.detail
          } catch {
            // non-JSON error body; keep the status-based message
          }
          setError(detail)
          return null
        }
        const result = (await response.json()) as UploadResult
        await listDocuments()
        return result
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed')
        return null
      } finally {
        setUploading(false)
      }
    },
    [sessionId, uploading, listDocuments],
  )

  useEffect(() => {
    void listDocuments()
  }, [listDocuments])

  return { documents, uploading, error, uploadDocument }
}
