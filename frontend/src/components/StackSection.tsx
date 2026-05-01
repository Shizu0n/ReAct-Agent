const stackRows = [
  ['Python 3.11', 'Runtime'],
  ['LangGraph 0.2', 'Agent orchestration'],
  ['FastAPI', 'REST + SSE API'],
  ['Pydantic', 'Input validation'],
  ['Tavily API', 'Web search tool'],
  ['Vercel', 'Frontend deployment'],
]

export function StackSection() {
  return (
    <section id="stack" className="border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)] py-[8vh]">
      <div className="mx-auto max-w-[1200px] px-[clamp(1.25rem,4vw,3rem)]">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-[var(--text-tertiary)]">
          Runtime choices
        </p>
        <h2 className="mt-4 text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[0.95] tracking-tight text-white">
          Built with
        </h2>

        <div className="mt-12 grid grid-cols-1 items-start gap-12 lg:grid-cols-[1fr_auto]">
          <div>
            {stackRows.map(([name, role]) => (
              <div key={name} className="flex items-center justify-between gap-6 border-b border-[var(--border-subtle)] py-4">
                <span className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-white">
                  {name}
                </span>
                <span className="text-right font-mono text-[0.65rem] text-[var(--text-tertiary)]">{role}</span>
              </div>
            ))}
          </div>

          <a
            href="https://github.com/Shizu0n/react-agent"
            target="_blank"
            rel="noreferrer"
            className="flex min-w-[280px] flex-col gap-5 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-tertiary)] p-6 transition-all duration-300 hover:border-[var(--accent-border)] hover:bg-[var(--bg-elevated)]"
          >
            <div className="flex items-center gap-3">
              <GithubIcon />
              <span className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-white">
                View Source
              </span>
            </div>
            <p className="text-[0.875rem] leading-[1.7] text-[var(--text-secondary)]">
              Full source, architecture docs, deployment notes, and tests on GitHub.
            </p>
            <span className="self-start rounded-xl border border-[var(--border-default)] bg-[var(--bg-secondary)] px-4 py-3 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-white transition-all duration-300 hover:border-white hover:bg-white hover:text-black">
              Open repository
            </span>
          </a>
        </div>
      </div>
    </section>
  )
}

function GithubIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.1 3.29 9.4 7.86 10.92.58.1.79-.25.79-.56v-2.17c-3.2.7-3.88-1.36-3.88-1.36-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.3 1.19-3.1-.12-.3-.52-1.48.11-3.08 0 0 .97-.31 3.17 1.18A10.96 10.96 0 0 1 12 5.96c.98 0 1.96.13 2.88.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.6.23 2.78.11 3.08.74.8 1.19 1.84 1.19 3.1 0 4.43-2.7 5.4-5.26 5.69.41.36.78 1.07.78 2.15v3.17c0 .31.21.67.8.56A11.52 11.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  )
}
