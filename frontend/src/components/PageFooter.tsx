export function PageFooter() {
  return (
    <footer id="about" className="border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)] py-8">
      <div className="mx-auto flex max-w-[1200px] flex-col items-start justify-between gap-4 px-[clamp(1.25rem,4vw,3rem)] sm:flex-row sm:items-center">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          ReAct Agent - inspectable reasoning demo
        </p>
        <div className="flex gap-6">
          <a
            href="https://shizu0n.vercel.app"
            className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)] transition-colors hover:text-[var(--accent-text)]"
          >
            About
          </a>
          <a
            href="https://huggingface.co/Shizu0n"
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[0.65rem] uppercase tracking-[0.14em] text-[var(--text-tertiary)] transition-colors hover:text-[var(--accent-text)]"
          >
            HuggingFace
          </a>
        </div>
      </div>
    </footer>
  )
}
