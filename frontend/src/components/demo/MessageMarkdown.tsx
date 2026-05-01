import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import clojure from 'react-syntax-highlighter/dist/esm/languages/prism/clojure'
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

type MessageMarkdownProps = {
  content: string
}

SyntaxHighlighter.registerLanguage('bash', bash)
SyntaxHighlighter.registerLanguage('clojure', clojure)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('typescript', typescript)
SyntaxHighlighter.registerLanguage('js', javascript)
SyntaxHighlighter.registerLanguage('ts', typescript)

const components: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className ?? '')
    const code = String(children).replace(/\n$/, '')

    if (match) {
      return (
        <SyntaxHighlighter
          PreTag="div"
          language={match[1]}
          style={oneDark}
          customStyle={{
            margin: '0.85rem 0',
            borderRadius: '0.85rem',
            border: '1px solid var(--border-subtle)',
            background: 'var(--bg-tertiary)',
            fontSize: '0.82rem',
          }}
        >
          {code}
        </SyntaxHighlighter>
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
