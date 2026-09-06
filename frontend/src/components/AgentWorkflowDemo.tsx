import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, BadgeCheck, ClipboardCheck, Cpu, Database, FileText, Gauge, GitMerge,
  Globe, History, LayoutGrid, Lock, Pause, Play, RefreshCcw, Route, ShieldCheck,
  Sparkles, TrainFront, AlertTriangle, Wrench, CheckSquare, RotateCcw,
  StepBack, StepForward,
} from 'lucide-react'
import {
  BANDS, EDGES, NODES, PHASE_OF, type GraphEdge, type GraphNode,
} from '../lib/workflowTopology'

const ICONS: Record<string, any> = {
  start: Play, validate: ClipboardCheck, maintenance: Wrench, traffic: TrainFront,
  priority: Gauge, merge: GitMerge, historical: History, rag: Database,
  web_research: Globe, evidence: ShieldCheck, candidate: LayoutGrid,
  optimize: Cpu, simulate: Activity, routing: Route, route_optimize: RefreshCcw,
  gate: Lock, validate_constraints: BadgeCheck, risk: AlertTriangle,
  fusion: Sparkles, report: FileText, end: CheckSquare,
}

const STEPS = [
  'start', 'validate', 'maintenance', 'traffic', 'priority', 'merge',
  'historical', 'rag', 'web_research', 'evidence', 'candidate', 'optimize',
  'simulate', 'routing', 'route_optimize', 'gate', 'validate_constraints',
  'risk', 'fusion', 'report', 'end',
]

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

const STATE_STYLE: Record<string, { fill: string; stroke: string; text: string }> = {
  idle:   { fill: 'rgba(255,255,255,0.05)',  stroke: 'rgba(148,163,184,0.45)', text: 'rgba(148,163,184,0.85)' },
  active: { fill: 'rgba(29,95,167,0.35)',     stroke: '#60A5FA',               text: '#EAF2FF' },
  done:   { fill: 'rgba(24,121,78,0.18)',     stroke: 'rgba(52,211,153,0.8)',  text: 'rgba(167,243,208,0.95)' },
}

const ORDER: Record<string, number> = {}
NODES.forEach((n, i) => (ORDER[n.id] = i))

const SPEEDS = [2200, 1300, 800]

const STEP_IDX: Record<string, number> = {}
STEPS.forEach((id, i) => (STEP_IDX[id] = i))

export default function AgentWorkflowDemo() {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const svgWrapRef = useRef<HTMLDivElement>(null)

  const phaseOfCurrent = useMemo(() => {
    const id = STEPS[step]
    return BANDS.find(b => b.id === PHASE_OF[id])?.label || ''
  }, [step])

  useEffect(() => {
    if (!playing) return
    const iv = setInterval(() => setStep(s => (s + 1) % STEPS.length), SPEEDS[speed])
    return () => clearInterval(iv)
  }, [playing, speed])

  useEffect(() => {
    if (!scrollRef.current || !svgWrapRef.current) return
    const node = NODES.find(n => n.id === STEPS[step])
    if (!node) return
    const scale = svgWrapRef.current.clientWidth / 1120
    const top = node.y * scale - scrollRef.current.clientHeight / 2 + 210
    scrollRef.current.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [step])

  const stepState = (id: string) => {
    const cur = STEP_IDX[id]
    if (cur < step) return 'done'
    if (cur === step) return 'active'
    return 'idle'
  }

  const edgeState = (e: GraphEdge): 'done' | 'active' | 'idle' => {
    const a = stepState(e.from)
    const b = stepState(e.to)
    if (a === 'done' && (b === 'done' || b === 'active')) return 'done'
    if (a === 'active') return 'active'
    return 'idle'
  }

  const edgeColor = (e: GraphEdge): string => {
    if (e.loop) return '#F59E0B'
    const s = edgeState(e)
    if (s === 'done') return '#34D399'
    if (s === 'active') return '#60A5FA'
    return 'rgba(148,163,184,0.35)'
  }

  const byId = useMemo(() => {
    const m: Record<string, GraphNode> = {}
    NODES.forEach(n => (m[n.id] = n))
    return m
  }, [])

  const advance = (delta: number) => setStep(s => (s + delta + STEPS.length) % STEPS.length)

  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 overflow-hidden">
      <div className="px-6 sm:px-10 pt-8 pb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="h-overline text-blue-300">Agentic Pipeline</p>
            <h3 className="text-2xl sm:text-3xl font-extrabold mt-2">Watch the AI think, step by step</h3>
            <p className="text-blue-100 mt-2 max-w-xl text-sm">
              The pipeline flows automatically in slow motion. Follow the highlighted node
              and read what each agent does before the plan reaches the officer.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPlaying(p => !p)} className="btn-rail w-10 h-10 !p-0 flex items-center justify-center" title={playing ? 'Pause' : 'Play'}>
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button onClick={() => { setPlaying(false); setStep(0) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center !bg-white/10 !border-white/20 !text-white" title="Restart">
              <RotateCcw className="w-4 h-4" />
            </button>
            <button onClick={() => { setPlaying(false); advance(-1) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center !bg-white/10 !border-white/20 !text-white" title="Previous">
              <StepBack className="w-4 h-4" />
            </button>
            <button onClick={() => { setPlaying(false); advance(1) }} className="btn-ghost w-10 h-10 !p-0 flex items-center justify-center !bg-white/10 !border-white/20 !text-white" title="Next">
              <StepForward className="w-4 h-4" />
            </button>
            <button
              onClick={() => setSpeed(s => (s + 1) % SPEEDS.length)}
              className="btn-ghost !bg-white/10 !border-white/20 !text-white px-3 py-2 text-xs font-semibold"
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
                      fill="rgba(147,197,253,0.04)" stroke="rgba(147,197,253,0.18)" strokeDasharray="5 7" />
                    <text x={x0 + 12} y={b.y0 + 17} fontSize="10" fontWeight="700" letterSpacing="1.5"
                      fill="rgba(147,197,253,0.85)" fontFamily="Inter, sans-serif">
                      {b.label.toUpperCase()}
                    </text>
                  </g>
                )
              })}

              {EDGES.map((e, i) => {
                const color = edgeColor(e)
                const dash = e.loop || e.dashed || e.to === 'fail' ? '6 6' : undefined
                return (
                  <path key={i} d={edgePath(e, byId)} fill="none" stroke={color} strokeWidth={e.loop ? 2 : 2.2}
                    strokeOpacity={color.startsWith('rgb') ? 0.5 : 0.95}
                    strokeDasharray={dash}
                    strokeDashoffset={e.loop ? 0 : undefined}
                    strokeLinecap="round"
                    style={color === '#34D399' || color === '#60A5FA' ? { animation: `dash-flow 0.9s linear infinite ${color === '#60A5FA' ? '' : 'reverse'}` } : undefined} />
                )
              })}

              {NODES.filter(n => n.id !== 'fail').map(n => {
                const st = stepState(n.id)
                const c = STATE_STYLE[st]
                const Icon = ICONS[n.id]
                const isTerminal = n.kind === 'start' || n.kind === 'end'
                const w = n.width || 168
                const h = isTerminal ? 32 : 50
                return (
                  <g key={n.id} transform={`translate(${n.x - w / 2}, ${n.y - h / 2})`}>
                    {st === 'active' && (
                      <circle cx={w / 2} cy={h / 2} r={Math.max(w, h) / 2 + 6} fill="none" stroke="#60A5FA"
                        strokeWidth={2.4} opacity={0.6} className="animate-ping" />
                    )}
                    <rect width={w} height={h} rx={isTerminal ? 16 : 12} fill={c.fill} stroke={c.stroke} strokeWidth={st === 'active' ? 2 : 1.4} />
                    <g transform={`translate(${isTerminal ? 14 : 48}, ${h / 2})`}>
                      <circle r={12} fill="rgba(255,255,255,0.12)" stroke={c.stroke} strokeOpacity={0.7} strokeWidth={1} />
                      <Icon x={-6.5} y={-6.5} width={13} height={13} color={c.text} strokeWidth={2} />
                    </g>
                    <text x={isTerminal ? 40 : 70} y={h / 2 + 4} fontSize={isTerminal ? 12.5 : 11.5}
                      fontWeight={st === 'active' ? 700 : 600} fill={c.text} fontFamily="Inter, sans-serif">
                      {n.label}
                    </text>
                    {st === 'done' && (
                      <text x={w - 20} y={h / 2 + 4} fontSize={13} fill="#34D399" fontWeight={700}>✓</text>
                    )}
                  </g>
                )
              })}
            </svg>
          </div>
        </div>

        {/* narration panel */}
        <div className="border-t lg:border-t-0 lg:border-l border-white/10 p-6 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs text-blue-300">
              STEP {String(step + 1).padStart(2, '0')} / {STEPS.length}
            </span>
            <span className="chip border border-amber-400/30 bg-amber-400/10 text-amber-300">
              {phaseOfCurrent.toUpperCase()}
            </span>
          </div>
          <p className="text-lg font-bold text-white">{byId[STEPS[step]]?.label || ''}</p>
          <p className="text-sm text-blue-100 mt-2 leading-relaxed">{DESCRIPTIONS[STEPS[step]]}</p>

          <div className="mt-auto pt-6">
            <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-400 to-emerald-400 transition-all duration-500"
                style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
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
    const x = Math.min(a.x, b.x) - 168
    return `M ${a.x - 84} ${a.y + 12} H ${x} V ${b.y - 25 + 10} H ${b.x + 84}`
  }
  if (e.to === 'fail' || e.from === 'fail') {
    const fx = byId.fail.x
    return `M ${a.x} ${a.y + 25} C ${(a.x + fx) / 2} ${a.y + 70}, ${(a.x + fx) / 2} ${b.y - 70}, ${fx - 84} ${b.y}`
  }
  if (a.y === b.y) {
    const x1 = a.x + 84
    const x2 = b.x - 84
    return `M ${x1} ${a.y} C ${x1 + (x2 - x1) / 2} ${a.y}, ${x2 - (x2 - x1) / 2} ${b.y}, ${x2} ${b.y}`
  }
  return `M ${a.x} ${a.y + 25} C ${a.x} ${a.y + 46}, ${b.x} ${b.y - 46}, ${b.x} ${b.y - 25}`
}