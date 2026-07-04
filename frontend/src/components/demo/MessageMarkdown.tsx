import { Suspense, lazy } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

// The Prism highlighter is the heaviest dependency in the bundle; load it only
// when an answer actually contains a fenced code block.
const CodeBlock = lazy(() => import('./CodeBlock'))

type MessageMarkdownProps = {
  content: string
}

function PlainCodeFallback({ code }: { code: string }) {
  return (
    <pre className="my-3 overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] p-3 font-mono text-[0.82rem] text-[var(--text-secondary)]">
      {code}
    </pre>
  )
}

const components: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className ?? '')
    const code = String(children).replace(/\n$/, '')

    if (match) {
      return (
        <Suspense fallback={<PlainCodeFallback code={code} />}>
          <CodeBlock language={match[1]} code={code} />
        </Suspense>
      )
    }

    return (
      <code className="rounded border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-1.5 py-0.5 font-mono text-[0.84em] text-[var(--accent-cyan)]" {...props}>
        {children}
      </code>
    )
  },
  a({ children, ...props }) {
    return (
      <a className="text-[var(--accent-cyan)] underline decoration-[var(--border-strong)] underline-offset-4 hover:text-[var(--accent-text)]" {...props}>
        {children}
      </a>
    )
  },
  table({ children }) {
    return (
      <div className="my-3 overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
        <table className="min-w-full divide-y divide-[var(--border-subtle)] text-left">{children}</table>
      </div>
    )
  },
  th({ children }) {
    return <th className="bg-[var(--bg-tertiary)] px-3 py-2 font-mono text-[0.72rem] uppercase text-[var(--text-primary)]">{children}</th>
  },
  td({ children }) {
    return <td className="border-t border-[var(--border-subtle)] px-3 py-2 text-[var(--text-secondary)]">{children}</td>
  },
}

export function MessageMarkdown({ content }: MessageMarkdownProps) {
  return (
    <div className="message-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
