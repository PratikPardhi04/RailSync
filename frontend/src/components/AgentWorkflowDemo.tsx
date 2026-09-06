import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, BadgeCheck, ClipboardCheck, Cpu, Database, FileText, Gauge, GitMerge,
  Globe, History, LayoutGrid, Lock, Pause, Play, RefreshCcw, Route, ShieldCheck,
  Sparkles, TrainFront, AlertTriangle, Wrench, CheckSquare, RotateCcw,
  StepBack, StepForward,
} from 'lucide-react'
import {
  BANDS, EDGES, NODES, NODE_H, NODE_W, PHASE_OF, type GraphEdge, type GraphNode,
} from '../lib/workflowTopology'

const ICONS: Record<string, any> = {
  start: Play, validate: ClipboardCheck, maintenance: Wrench, traffic: TrainFront,
  priority: Gauge, merge: GitMerge, historical: History, rag: Database,
  web_research: Globe, evidence: ShieldCheck, candidate: LayoutGrid,
  optimize: Cpu, simulate: Activity, routing: Route, route_optimize: RefreshCcw,
  gate: Lock, validate_constraints: BadgeCheck, risk: AlertTriangle,
  fusion: Sparkles, report: FileText, end: CheckSquare,
}

const DESCRIPTIONS: Record<string, string> = {
  start: 'Engineer submits the block — section, track, work type, preferred window and safety instructions.',
  validate: 'Data validation. Checks the request is complete, the location is real and the window is physically feasible.',
  maintenance: 'Maintenance agent sizes the job — machines, crew, ballast and rail-pad needs on that track.',
  traffic: 'Traffic agent scans the full day\u2019s train timetable on the section.',
  priority: 'Priority agent flags premium trains — Rajdhani, Shatabdi and Vande Bharat get top protection.',
  merge: 'Merge. One combined operational picture of the busy section.',
  historical: 'Historical agent recalls past blocks and known trouble spots on this corridor.',
  rag: 'RAG retrieve — pulls maintenance SOPs and rules from the knowledge base.',
  web_research: 'Web research — Tavily gathers public evidence (advisory only, never decides).',
  evidence: 'Evidence check — validates the web research before it is used.',
  candidate: 'Candidate generation — proposes a shortlist of candidate block windows.',
  optimize: 'CP-SAT — Google OR-Tools deterministically selects the safest, least-impact window.',
  simulate: 'Simulate — runs every train against the block: delays, holds and diversions.',
  routing: 'Routing agent proposes diversions, e.g. the Yerwada ALT-SK-1 bypass.',
  route_optimize: 'Route optimizer computes whether each reroute is actually feasible.',
  gate: 'Hard-conflict gate — if a premium train would be blocked, it auto-replans (max 3 tries) before anything reaches an officer.',
  validate_constraints: 'Constraint validation — re-checks every rule and regenerates candidates if anything breaks.',
  risk: 'Risk agent — risk and compliance score for the final window.',
  fusion: 'Decision fusion — advisory RECOMMEND_APPROVE / RECOMMEND_REVIEW (never overrides CP-SAT).',
  report: 'Report — the officer-ready document: window, affected trains, delays, risk and confidence.',
  end: 'Pending review — sent to the officer, who can approve or reject (rejection triggers a live replan).',
}

// An ordered list of phases. Each phase activates one or more nodes at the
// same time. The Maintenance / Traffic / Priority perception agents run in
// parallel after validation, so they share a single phase.
const PHASES: { nodes: string[]; description: string; parallel?: boolean }[] = [
  { nodes: ['start'], description: DESCRIPTIONS.start },
  { nodes: ['validate'], description: DESCRIPTIONS.validate },
  {
    nodes: ['maintenance', 'traffic', 'priority'],
    parallel: true,
    description: 'Three perception agents examine the request in parallel — maintenance sizes the job, traffic scans the timetable, and priority flags the premium trains.',
  },
  { nodes: ['merge'], description: DESCRIPTIONS.merge },
  { nodes: ['historical'], description: DESCRIPTIONS.historical },
  { nodes: ['rag'], description: DESCRIPTIONS.rag },
  { nodes: ['web_research'], description: DESCRIPTIONS.web_research },
  { nodes: ['evidence'], description: DESCRIPTIONS.evidence },
  { nodes: ['candidate'], description: DESCRIPTIONS.candidate },
  { nodes: ['optimize'], description: DESCRIPTIONS.optimize },
  { nodes: ['simulate'], description: DESCRIPTIONS.simulate },
  { nodes: ['routing'], description: DESCRIPTIONS.routing },
  { nodes: ['route_optimize'], description: DESCRIPTIONS.route_optimize },
  { nodes: ['gate'], description: DESCRIPTIONS.gate },
  { nodes: ['validate_constraints'], description: DESCRIPTIONS.validate_constraints },
  { nodes: ['risk'], description: DESCRIPTIONS.risk },
  { nodes: ['fusion'], description: DESCRIPTIONS.fusion },
  { nodes: ['report'], description: DESCRIPTIONS.report },
  { nodes: ['end'], description: DESCRIPTIONS.end },
]

// node id -> phase index
const PHASE_IDX: Record<string, number> = {}
PHASES.forEach((p, i) => p.nodes.forEach(n => (PHASE_IDX[n] = i)))

// light theme node states (on white card)
const STATE_STYLE: Record<string, { fill: string; stroke: string; text: string }> = {
  idle:   { fill: 'rgba(244,246,248,0.75)', stroke: 'rgba(148,163,184,0.7)', text: '#64748B' },
  active: { fill: 'rgba(29,95,167,0.14)',    stroke: '#1D5FA7',               text: '#123B66' },
  done:   { fill: 'rgba(24,121,78,0.14)',    stroke: '#18794E',               text: '#14563A' },
}

const SPEEDS = [2200, 1300, 800]

export default function AgentWorkflowDemo() {
  const [phase, setPhase] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const svgWrapRef = useRef<HTMLDivElement>(null)

  const activePhase = PHASES[phase]
  const phaseOfCurrent = useMemo(() => {
    const id = activePhase.nodes[0]
    return BANDS.find(b => b.id === PHASE_OF[id])?.label || ''
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

  useEffect(() => {
    if (!playing) return
    const iv = setInterval(() => setPhase(s => (s + 1) % PHASES.length), SPEEDS[speed])
    return () => clearInterval(iv)
  }, [playing, speed])

  useEffect(() => {
    if (!scrollRef.current || !svgWrapRef.current) return
    const node = NODES.find(n => n.id === activePhase.nodes[0])
    if (!node) return
    const wrap = svgWrapRef.current
    const scale = wrap.clientWidth / 1120
    const top = node.y * scale - scrollRef.current.clientHeight / 2 + 210
    scrollRef.current.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [phase])

  const nodeState = (id: string) => {
    const cur = PHASE_IDX[id]
    if (cur === undefined) return 'idle'
    if (cur < phase) return 'done'
    if (cur === phase) return 'active'
    return 'idle'
  }

  const edgeState = (e: GraphEdge): 'done' | 'active' | 'idle' => {
    const a = nodeState(e.from)
    const b = nodeState(e.to)
    if (a === 'done' && (b === 'done' || b === 'active')) return 'done'
    if (a === 'active') return 'active'
    return 'idle'
  }

  const edgeColor = (e: GraphEdge): string => {
    if (e.loop) return '#A15C00'
    const s = edgeState(e)
    if (s === 'done') return '#18794E'
    if (s === 'active') return '#1D5FA7'
    return 'rgba(148,163,184,0.5)'
  }

  const byId = useMemo(() => {
    const m: Record<string, GraphNode> = {}
    NODES.forEach(n => (m[n.id] = n))
    return m
  }, [])

  const advance = (delta: number) => setPhase(s => (s + delta + PHASES.length) % PHASES.length)

  const phaseNodes = activePhase.nodes
  const phaseLabel = phaseNodes.length === 1
    ? (byId[phaseNodes[0]]?.label || '')
    : phaseNodes.map(n => byId[n]?.label).join(', ')

  return (
    <div className="rounded-3xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-6 sm:px-10 pt-8 pb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="h-overline">Agentic Pipeline</p>
            <h3 className="text-2xl sm:text-3xl font-extrabold mt-2 text-gray-900">Watch the AI think, step by step</h3>
            <p className="text-gray-600 mt-2 max-w-xl text-sm">
              The pipeline flows automatically in slow motion. Follow the highlighted node
              and read what each agent does before the plan reaches the officer.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPlaying(p => !p)} className="btn-rail w-10 h-10 !p-0 flex items-center justify-center" title={playing ? 'Pause' : 'Play'}>
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button onClick={() => { setPlaying(false); setPhase(0) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center" title="Restart">
              <RotateCcw className="w-4 h-4" />
            </button>
            <button onClick={() => { setPlaying(false); advance(-1) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center" title="Previous">
              <StepBack className="w-4 h-4" />
            </button>
            <button onClick={() => { setPlaying(false); advance(1) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center" title="Next">
              <StepForward className="w-4 h-4" />
            </button>
            <button
              onClick={() => setSpeed(s => (s + 1) % SPEEDS.length)}
              className="btn-ghost px-3 py-2 text-xs font-semibold"
              title="Playback speed"
            >
              {['1×', '2×', '3×'][speed]}
            </button>
          </div>
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[1fr_320px] gap-0">
        {/* flow diagram */}
        <div ref={scrollRef} className="relative max-h-[520px] overflow-y-auto px-4 pb-6 pt-2">
          <div ref={svgWrapRef}>
            <svg viewBox="0 0 1120 1710" className="w-full h-auto select-none" style={{ display: 'block' }}>
              {BANDS.map(b => {
                const inBand = NODES.filter(n => PHASE_OF[n.id] === b.id)
                const xs = inBand.map(n => n.x - 84)
                const xe = inBand.map(n => n.x + 84)
                const x0 = Math.min(...xs) - 12
                const x1 = Math.max(...xe) + 12
                return (
                  <g key={b.id}>
                    <rect x={x0} y={b.y0} width={x1 - x0} height={b.y1 - b.y0} rx={14}
                      fill="rgba(29,95,167,0.03)" stroke="rgba(29,95,167,0.18)" strokeDasharray="5 7" />
                    <text x={x0 + 12} y={b.y0 + 17} fontSize="10" fontWeight="700" letterSpacing="1.5"
                      fill={b.accent} fillOpacity="0.85" fontFamily="Inter, sans-serif">
                      {b.label.toUpperCase()}
                    </text>
                  </g>
                )
              })}

              {EDGES.map((e, i) => {
                const color = edgeColor(e)
                const active = color === '#18794E' || color === '#1D5FA7'
                return (
                  <path key={i} d={edgePath(e, byId)} fill="none" stroke={color} strokeWidth={e.loop ? 2 : 2.2}
                    strokeOpacity={active ? 0.95 : 0.5}
                    strokeDasharray={e.loop || e.dashed || e.to === 'fail' ? '6 6' : undefined}
                    strokeLinecap="round"
                    style={active ? { animation: `dash-flow 0.9s linear infinite ${color === '#1D5FA7' ? '' : 'reverse'}` } : undefined} />
                )
              })}

              {NODES.filter(n => n.id !== 'fail').map(n => {
                const st = nodeState(n.id)
                const c = STATE_STYLE[st]
                const Icon = ICONS[n.id]
                const isTerminal = n.kind === 'start' || n.kind === 'end'
                const w = n.width || NODE_W
                const h = isTerminal ? 32 : NODE_H
                return (
                  <g key={n.id} transform={`translate(${n.x - w / 2}, ${n.y - h / 2})`}>
                    {st === 'active' && (
                      <circle cx={w / 2} cy={h / 2} r={Math.max(w, h) / 2 + 6} fill="none" stroke="#1D5FA7"
                        strokeWidth={2.4} opacity={0.5} className="animate-ping" />
                    )}
                    <rect width={w} height={h} rx={isTerminal ? 16 : 12} fill={c.fill} stroke={c.stroke} strokeWidth={st === 'active' ? 2 : 1.4} />
                    <g transform={`translate(${isTerminal ? 14 : 48}, ${h / 2})`}>
                      <circle r={12} fill="rgba(255,255,255,0.85)" stroke={c.stroke} strokeOpacity={0.6} strokeWidth={1} />
                      <Icon x={-6.5} y={-6.5} width={13} height={13} color={c.text} strokeWidth={2} />
                    </g>
                    <text x={isTerminal ? 40 : 70} y={h / 2 + 4} fontSize={isTerminal ? 12.5 : 11.5}
                      fontWeight={st === 'active' ? 700 : 600} fill={c.text} fontFamily="Inter, sans-serif">
                      {n.label}
                    </text>
                    {st === 'done' && (
                      <text x={w - 20} y={h / 2 + 4} fontSize={13} fill="#18794E" fontWeight={700}>✓</text>
                    )}
                  </g>
                )
              })}
            </svg>
          </div>
        </div>

        {/* narration panel */}
        <div className="border-t lg:border-t-0 lg:border-l border-gray-200 bg-gray-50 p-6 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs text-gray-500">
              STEP {String(phase + 1).padStart(2, '0')} / {PHASES.length}
            </span>
            <span className="chip border border-amber-300 bg-amber-50 text-amber-700">
              {phaseOfCurrent.toUpperCase()}
            </span>
          </div>
          <p className="text-lg font-bold text-gray-900">{phaseLabel}</p>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed">{activePhase.description}</p>

          <div className="mt-auto pt-6">
            <div className="h-1.5 rounded-full bg-gray-200 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-railway-accent to-emerald-500 transition-all duration-500"
                style={{ width: `${((phase + 1) / PHASES.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function edgePath(e: GraphEdge, byId: Record<string, GraphNode>): string {
  const a = byId[e.from]
  const b = byId[e.to]
  if (!a || !b) return ''
  if (e.loop) {
    const x = Math.min(a.x, b.x) - NODE_W / 2 - 84
    return `M ${a.x - NODE_W / 2} ${a.y + 12} H ${x} V ${b.y - NODE_H / 2 + 10} H ${b.x + NODE_W / 2}`
  }
  if (e.to === 'fail' || e.from === 'fail') {
    const fx = byId.fail.x
    return `M ${a.x} ${a.y + NODE_H / 2} C ${(a.x + fx) / 2} ${a.y + 70}, ${(a.x + fx) / 2} ${b.y - 70}, ${fx - NODE_W / 2} ${b.y}`
  }
  if (a.y === b.y) {
    const x1 = a.x + NODE_W / 2
    const x2 = b.x - NODE_W / 2
    return `M ${x1} ${a.y} C ${x1 + (x2 - x1) / 2} ${a.y}, ${x2 - (x2 - x1) / 2} ${b.y}, ${x2} ${b.y}`
  }
  return `M ${a.x} ${a.y + NODE_H / 2} C ${a.x} ${a.y + 46}, ${b.x} ${b.y - 46}, ${b.x} ${b.y - NODE_H / 2}`
}