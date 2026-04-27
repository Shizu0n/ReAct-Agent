import { DemoSection } from './components/DemoSection'
import { HeroSection } from './components/HeroSection'
import { HowItWorksSection } from './components/HowItWorksSection'
import { PageFooter } from './components/PageFooter'
import { StackSection } from './components/StackSection'
import { useAgent } from './hooks/useAgent'

function App() {
  const { state, sendQuery } = useAgent()

  return (
    <div className="min-h-screen bg-black text-white">
      <HeroSection />
      <DemoSection state={state} sendQuery={sendQuery} />
      <HowItWorksSection />
      <StackSection />
      <PageFooter />
    </div>
  )
}

export default App
