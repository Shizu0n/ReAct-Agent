import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import clojure from 'react-syntax-highlighter/dist/esm/languages/prism/clojure'
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

SyntaxHighlighter.registerLanguage('bash', bash)
SyntaxHighlighter.registerLanguage('clojure', clojure)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('typescript', typescript)
SyntaxHighlighter.registerLanguage('js', javascript)
SyntaxHighlighter.registerLanguage('ts', typescript)

type CodeBlockProps = {
  language: string
  code: string
}

// Loaded lazily from MessageMarkdown: the highlighter plus its Prism grammars
// are the heaviest part of the bundle and only needed once a code block renders.
export default function CodeBlock({ language, code }: CodeBlockProps) {
  return (
    <SyntaxHighlighter
      PreTag="div"
      language={language}
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
