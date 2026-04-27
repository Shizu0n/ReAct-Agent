export function PageFooter() {
  return (
    <footer className="border-t border-[#111] py-6">
      <div className="mx-auto flex max-w-[1200px] flex-col items-start justify-between gap-4 px-[clamp(1.25rem,4vw,3rem)] sm:flex-row sm:items-center">
        <p className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[#5b5b5b]">
          ReAct Agent — ML Engineering Portfolio
        </p>
        <div className="flex gap-6">
          <a
            href="https://shizu0n.vercel.app"
            className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[#5b5b5b] transition-colors hover:text-white"
          >
            ← Portfolio
          </a>
          <a
            href="https://huggingface.co/Shizu0n"
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[#5b5b5b] transition-colors hover:text-white"
          >
            HuggingFace →
          </a>
        </div>
      </div>
    </footer>
  )
}
