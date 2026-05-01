import { HeroSection } from './HeroSection'
import { HowItWorksSection } from './HowItWorksSection'
import { PageFooter } from './PageFooter'
import { StackSection } from './StackSection'

type PortfolioViewProps = {
  onOpenChat: () => void
}

export function PortfolioView({ onOpenChat }: PortfolioViewProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <HeroSection onOpenChat={onOpenChat} />
      <HowItWorksSection />
      <StackSection />
      <PageFooter />
    </div>
  )
}
