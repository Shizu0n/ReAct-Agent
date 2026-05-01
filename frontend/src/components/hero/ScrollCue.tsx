import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowDown } from 'lucide-react'

type ScrollCueProps = {
  hidden?: boolean
}

export function ScrollCue({ hidden = false }: ScrollCueProps) {
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const onScroll = () => setDismissed(true)
    const timeout = window.setTimeout(() => setDismissed(true), 6200)

    window.addEventListener('scroll', onScroll, { once: true, passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.clearTimeout(timeout)
    }
  }, [])

  return (
    <AnimatePresence>
      {!dismissed && !hidden ? (
        <motion.div
          className="pointer-events-none absolute bottom-8 left-1/2 flex -translate-x-1/2 items-center gap-2 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-[var(--text-tertiary)]"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.35 }}
        >
          <motion.span
            animate={{ y: [0, 5, 0] }}
            transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
          >
            Scroll
          </motion.span>
          <ArrowDown className="h-3.5 w-3.5" />
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
