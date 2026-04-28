const nodes = [
  { id: 'thought', label: 'THOUGHT', caption: 'reason', x: 240, y: 70, w: 150, h: 58 },
  { id: 'action', label: 'ACTION', caption: 'tool call', x: 78, y: 322, w: 142, h: 58 },
  { id: 'observe', label: 'OBSERVE', caption: 'result', x: 420, y: 322, w: 150, h: 58 },
  { id: 'llm', label: 'LLM', caption: 'loop core', x: 268, y: 210, w: 104, h: 74 },
] as const

const paths = [
  {
    id: 'thought-action',
    label: 'plan',
    d: 'M252 130 C218 178 170 244 150 318',
  },
  {
    id: 'action-observe',
    label: 'execute',
    d: 'M222 350 C286 390 360 390 418 350',
  },
  {
    id: 'observe-thought',
    label: 'feedback',
    d: 'M500 318 C480 235 420 166 378 130',
  },
  {
    id: 'llm-pulse',
    label: 'reasoning core',
    d: 'M318 208 C305 180 305 154 318 130 M318 286 C318 302 318 314 318 322',
  },
] as const

const particleLoopPath =
  'M252 130 C218 178 170 244 150 318 C178 372 326 406 418 350 C476 308 465 210 378 130 C340 104 288 106 252 130'

const particles = [
  { id: 'lead', begin: '0s', radius: 4.4 },
  { id: 'mid', begin: '-1.8s', radius: 3.8 },
  { id: 'tail', begin: '-3.6s', radius: 3.2 },
] as const

export function AgentFlowPreview() {
  return (
    <div className="agent-flow-shell" aria-label="Animated ReAct reasoning flow">
      <div className="agent-flow-status">
        <span className="agent-flow-status-dot" />
        <span>react loop</span>
      </div>

      <svg className="react-loop-map" viewBox="0 0 660 520" role="img" aria-hidden="true">
        <defs>
          <linearGradient id="loopLine" x1="0%" x2="100%" y1="0%" y2="0%">
            <stop offset="0%" stopColor="rgba(103,232,249,0.08)" />
            <stop offset="52%" stopColor="rgba(103,232,249,0.55)" />
            <stop offset="100%" stopColor="rgba(165,180,252,0.12)" />
          </linearGradient>
          <filter id="loopGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="loopArrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="rgba(103,232,249,0.62)" />
          </marker>
        </defs>

        <g className="loop-orbit" filter="url(#loopGlow)">
          {paths.map((path) => (
            <path key={path.id} d={path.d} markerEnd={path.id === 'llm-pulse' ? undefined : 'url(#loopArrow)'} />
          ))}
        </g>

        <g className="loop-particles" filter="url(#loopGlow)">
          {particles.map((particle) => (
            <circle key={particle.id} r={particle.radius}>
              <animateMotion
                begin={particle.begin}
                dur="5.4s"
                repeatCount="indefinite"
                path={particleLoopPath}
              />
            </circle>
          ))}
        </g>

        <g className="llm-breath" filter="url(#loopGlow)">
          <circle cx="320" cy="248" r="58" />
          <circle cx="320" cy="248" r="82" />
        </g>

        <g className="loop-nodes">
          {nodes.map((node) => (
            <g key={node.id} className={`loop-node loop-node-${node.id}`}>
              <rect x={node.x} y={node.y} width={node.w} height={node.h} rx="12" />
              <text className="loop-node-label" x={node.x + node.w / 2} y={node.y + 25} textAnchor="middle">
                {node.label}
              </text>
              <text className="loop-node-caption" x={node.x + node.w / 2} y={node.y + 43} textAnchor="middle">
                {node.caption}
              </text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  )
}
