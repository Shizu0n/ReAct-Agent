import type { SVGProps } from 'react'

type ProjectMarkProps = SVGProps<SVGSVGElement> & {
  title?: string
}

export function ProjectMark({ title, ...props }: ProjectMarkProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M7.75 8.5h6.9c2.7 0 5.1 1.73 5.94 4.3l.36 1.1"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <path
        d="M24.25 23.5h-6.9a6.24 6.24 0 0 1-5.94-4.3l-.36-1.1"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <path
        d="m20.35 10 3.3 3.6-3.3 3.6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <path
        d="m11.65 14.8-3.3 3.6 3.3 3.6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <circle cx="7" cy="8.5" r="2.55" fill="currentColor" />
      <circle cx="25" cy="23.5" r="2.55" fill="currentColor" />
      <circle cx="16" cy="16" r="1.95" fill="currentColor" opacity="0.72" />
    </svg>
  )
}
