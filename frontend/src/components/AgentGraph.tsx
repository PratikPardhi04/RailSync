import { useMemo } from 'react'
import {
  Activity, BadgeCheck, ClipboardCheck, Cpu, Database, FileText, Gauge, GitMerge,
  Globe, History, LayoutGrid, Lock, Octagon, RefreshCcw, Route, ShieldCheck,
  Sparkles, TrainFront, AlertTriangle, Wrench, Play, CheckSquare,
} from 'lucide-react'
import {
  BANDS, EDGES, NODES, NODE_H, NODE_W, PHASE_OF,
  type GraphEdge, type GraphNode, type NodeState,
} from '../lib/workflowTopology'

export interface StepRow {
  agent: string
  status: string
  data?: any
}

const ICONS: Record<string, any> = {
  start: Play, validate: ClipboardCheck, maintenance: Wrench, traffic: TrainFront,
  priority: Gauge, merge: GitMerge, historical: History, rag: Database,
  web_research: Globe, evidence: ShieldCheck, candidate: LayoutGrid,
  optimize: Cpu, simulate: Activity, routing: Route, route_optimize: RefreshCcw,
  gate: Lock, validate_constraints: BadgeCheck, risk: AlertTriangle,
  fusion: Sparkles, report: FileText, fail: Octagon, end: CheckSquare,
}

const NODE_COLOR: Record<NodeState, { fill: string; stroke: string; text: string; glow?: string }> = {
  idle:   { fill: 'rgba(244,246,248,0.75)', stroke: 'rgba(148,163,184,0.9)', text: '#64748B' },
  queued: { fill: 'rgba(238,243,247,0.95)', stroke: '#94A3B8', text: '#4B5563' },
  active: { fill: 'rgba(29,95,167,0.12)', stroke: '#1D5FA7', text: '#123B66' },
  done:   { fill: 'rgba(24,121,78,0.12)', stroke: '#18794E', text: '#14563A' },
  failed: { fill: 'rgba(179,38,30,0.12)', stroke: '#B3261E', text: '#8C1F1A' },
}

const STEP_TO_NODE: Record<string, string> = {
  request_received: 'start',
  data_validation: 'validate',
  maintenance_agent: 'maintenance',
  traffic_agent: 'traffic',
  priority_agent: 'priority',
  historical_agent: 'historical',
  rag_retrieval: 'rag',
  web_research: 'web_research',
  evidence_validation: 'evidence',
  candidate_generation: 'candidate',
  cp_sat_optimization: 'optimize',
  simulation: 'simulate',
  routing_analysis: 'routing',
  route_optimization: 'route_optimize',
  hard_conflict_gate: 'gate',
  constraint_validation: 'validate_constraints',
  risk_compliance: 'risk',
  decision_fusion: 'fusion',
  report_generation: 'report',
  workflow_failed: 'fail',
}

function resolveStates(steps: StepRow[], failed: boolean): Record<string, NodeState> {
  const state: Record<string, NodeState> = {}
  NODES.forEach(n => (state[n.id] = 'idle'))

  const nameToNode: Record<string, string> = { ...STEP_TO_NODE }
  NODES.forEach(n => { if (n.stepName && !nameToNode[n.stepName]) nameToNode[n.stepName] = n.id })

  const lastFor: Record<string, StepRow> = {}
  for (const s of steps) {
    const id = nameToNode[s.agent] || s.agent
    if (NODES.some(n => n.id === id)) lastFor[id] = s
  }

  const orderIndex: Record<string, number> = {}
  NODES.forEach((n, i) => (orderIndex[n.id] = i))

  // terminal failure colours the fail node + the step that failed
  if (failed) state.fail = 'failed'
  for (const id of Object.keys(lastFor)) {
    const s = lastFor[id]
    if (s.status === 'failed') state[id] = 'failed'
  }

  const activeId = Object.keys(lastFor).find(id => lastFor[id].status === 'in_progress')
  const reached = Object.keys(lastFor).filter(id => state[id] !== 'failed')
  if (reached.length > 0) {
    const deepest = Math.max(...reached.map(id => orderIndex[id]))
    for (const n of NODES) {
      if (n.kind === 'start' || n.kind === 'end' || n.kind === 'fail') continue
      if (orderIndex[n.id] <= deepest && state[n.id] !== 'failed' && n.id !== 'validate_constraints') {
        state[n.id] = 'done'
      }
    }
  }

  for (const id of Object.keys(lastFor)) {
    const s = lastFor[id]
    if (s.status === 'in_progress') state[id] = 'active'
  }
  if (activeId && state[activeId] !== 'failed') state[activeId] = 'active'

  // report ready => everything done (except the fail sink)
  if (state.report === 'done' && !failed) {
    NODES.forEach(n => { if (state[n.id] !== 'failed' && n.id !== 'fail') state[n.id] = 'done' })
  }
  return state
}

function edgePath(e: GraphEdge, byId: Record<string, GraphNode>): string {
  const a = byId[e.from]
  const b = byId[e.to]
  if (!a || !b) return ''

  if (e.loop) {
    // elbow out to the left of the source, back into the target
    const x = Math.min(a.x, b.x) - NODE_W / 2 - 84
    return `M ${a.x - NODE_W / 2} ${a.y + 12} H ${x} V ${b.y - NODE_H / 2 + 10} H ${b.x + NODE_W / 2}`
  }
  if (e.to === 'fail' || e.from === 'fail') {
    const fx = byId.fail.x
    const x = a.x
    return `M ${x} ${a.y + NODE_H / 2} C ${(x + fx) / 2} ${a.y + 70}, ${(x + fx) / 2} ${b.y - 70}, ${fx - NODE_W / 2} ${b.y}`
  }
  if (a.y === b.y) {
    // horizontal fan-out row: maintenance/priority edges to/from merge are vertical; validate fan-out is curved
    const x1 = a.x + NODE_W / 2
    const x2 = b.x - NODE_W / 2
    return `M ${x1} ${a.y} C ${x1 + (x2 - x1) / 2} ${a.y}, ${x2 - (x2 - x1) / 2} ${b.y}, ${x2} ${b.y}`
  }
  // vertical spine
  return `M ${a.x} ${a.y + NODE_H / 2} C ${a.x} ${a.y + 46}, ${b.x} ${b.y - 46}, ${b.x} ${b.y - NODE_H / 2}`
}

interface AgentGraphProps {
  steps: StepRow[]
  failed?: boolean
  selected?: string | null
  onSelect?: (id: string | null) => void
}

export default function AgentGraph({ steps, failed = false, selected, onSelect }: AgentGraphProps) {
  const byId = useMemo(() => {
    const m: Record<string, GraphNode> = {}
    NODES.forEach(n => (m[n.id] = n))
    return m
  }, [])

  const states = useMemo(() => resolveStates(steps, failed), [steps, failed])

  const edgeActive = (e: GraphEdge): boolean => {
    const a = states[e.from]
    const b = states[e.to]
    if (e.to === 'fail') return e.from === 'gate' || e.from === 'validate_constraints' || e.from === 'optimize' ? a === 'failed' : false
    if (e.from === 'fail') return false
    if (a === 'failed' || b === 'failed') return false
    if (a === 'active') return true
    if (a === 'done') return b === 'active' || b === 'done'
    return false
  }

  return (
    <div className="relative">
      <svg viewBox="0 0 1120 1710" className="w-full h-auto select-none" style={{ display: 'block' }}>
        {/* phase bands */}
        {BANDS.map(b => {
          const inBand = NODES.filter(n => PHASE_OF[n.id] === b.id)
          const xs = inBand.map(n => n.x - NODE_W / 2)
          const xe = inBand.map(n => n.x + (n.width || NODE_W) / 2)
          const x0 = Math.min(...xs) - 16
          const x1 = Math.max(...xe) + 16
          return (
            <g key={b.id}>
              <rect x={x0} y={b.y0} width={x1 - x0} height={b.y1 - b.y0} rx={14} fill={b.accent}
                fillOpacity="0.035" stroke={b.accent} strokeOpacity="0.16" strokeDasharray="5 7" />
              <text x={x0 + 12} y={b.y0 + 17} fontSize="10" fontWeight="700" letterSpacing="1.5"
                fill={b.accent} fillOpacity="0.8" fontFamily="Inter, sans-serif">
                {b.label.toUpperCase()}
              </text>
            </g>
          )
        })}

        {/* edges */}
        {EDGES.map((e, i) => {
          const act = edgeActive(e)
          const isFailEdge = e.to === 'fail' || e.from === 'fail'
          const color = isFailEdge ? '#B3261E' : act ? (e.loop ? '#A15C00' : '#1D5FA7') : '#94A3B8'
          const width = isFailEdge ? 2 : act ? 2.6 : 2
          const dashed = e.loop || e.dashed || isFailEdge
          return (
            <g key={i}>
              <path d={edgePath(e, byId)} fill="none" stroke={color} strokeWidth={width}
                strokeOpacity={act ? 0.95 : 0.4} strokeDasharray={dashed ? '6 6' : undefined}
                strokeLinecap="round"
                style={act && !isFailEdge ? { strokeDasharray: dashed ? '6 6' : '10 8', animation: `dash-flow 0.8s linear infinite ${dashed ? '' : 'reverse'}` } : undefined} />
              {e.label && !isFailEdge && (
                <text x={(byId[e.to].x + byId[e.from].x) / 2} y={Math.min(byId[e.to].y, byId[e.from].y) - 26}
                  textAnchor="middle" fontSize="9" fontWeight="600" letterSpacing="0.5"
                  fill={act ? '#A15C00' : '#64748B'} fontFamily="Inter, sans-serif">
                  {e.label}
                </text>
              )}
            </g>
          )
        })}

        {/* nodes */}
        {NODES.map(n => {
          const st = states[n.id] || 'idle'
          const c = NODE_COLOR[st]
          const Icon = ICONS[n.id]
          const isTerminal = n.kind === 'start' || n.kind === 'end'
          const isFail = n.kind === 'fail'
          const w = n.width || NODE_W
          const h = isTerminal ? 32 : NODE_H
          const isSelected = selected === n.id
          return (
            <g key={n.id} transform={`translate(${n.x - w / 2}, ${n.y - h / 2})`}
              onClick={() => onSelect?.(n.id)} style={{ cursor: 'pointer' }}>
              {(st === 'active') && (
                <circle cx={w / 2} cy={h / 2} r={Math.max(w, h) / 2 + 6} fill="none" stroke={c.stroke}
                  strokeWidth={2} opacity={0.5} className="animate-ping" />
              )}
              <rect width={w} height={h} rx={isTerminal ? 16 : 13}
                fill={c.fill} stroke={isSelected ? '#1D5FA7' : c.stroke} strokeWidth={isSelected ? 2 : 1.6}
                style={c.glow ? { filter: `drop-shadow(0 0 9px ${c.glow})` } : undefined} />
              <g transform={`translate(${isTerminal ? 14 : 48}, ${h / 2})`}>
                <circle r={12} fill="rgba(255,255,255,0.85)" stroke={c.stroke} strokeOpacity={0.5} strokeWidth={1} />
                <Icon x={-6.5} y={-6.5} width={13} height={13} color={c.text} strokeWidth={2} />
              </g>
              <text x={isTerminal ? 40 : 70} y={h / 2 + 4} fontSize={isTerminal ? 12.5 : 11.5}
                fontWeight={st === 'active' ? 700 : 600} fill={c.text} fontFamily="Inter, sans-serif">
                {n.label}
              </text>
              {st === 'done' && !isFail && (
                <text x={w - 20} y={h / 2 + 4} fontSize={13} fill="#18794E" fontWeight={700}>✓</text>
              )}
              {isFail && st === 'failed' && (
                <text x={w - 28} y={h / 2 + 4} fontSize={13} fill="#B3261E" fontWeight={700}>✕</text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}