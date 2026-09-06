import { useState } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, BookOpen, CheckCircle2, ClipboardCheck,
  Clock, Cpu, Database, FileText, FlaskConical, Gauge, GitBranch, Globe, History,
  Layers, Lightbulb, ShieldCheck, Sparkles, Timer, TrainFront, TrendingUp,
  XCircle,
} from 'lucide-react'
import type { OfficerReport as OfficerReportData, ReportData, BlockPlan } from '../types'
import StatusBadge, { RiskBadge } from './StatusBadge'

interface Props {
  rd?: ReportData
  plan?: BlockPlan
  approving?: boolean
  canDecide?: boolean
  readOnly?: boolean
  onApprove?: () => void
  onReject?: () => void
}

export default function OfficerReport({
  rd, plan, approving, canDecide, readOnly, onApprove, onReject,
}: Props) {
  const or = rd?.officer_report
  const [active, setActive] = useState<string | null>(null)
  if (!or) return <LegacyReport rd={rd} plan={plan} />

  const sections = [
    { id: 'executive', no: 1, title: 'Executive Recommendation', icon: FileText, render: () => <ExecSection or={or} /> },
    { id: 'why', no: 2, title: 'Why This Block', icon: Lightbulb, render: () => <WhySection or={or} /> },
    { id: 'train-impact', no: 3, title: 'Train Impact', icon: TrainFront, render: () => <TrainImpactSection or={or} /> },
    { id: 'alternatives', no: 4, title: 'Alternative Windows', icon: Clock, render: () => <AltWindowsSection or={or} /> },
    { id: 'routing', no: 5, title: 'Routing & Regulation', icon: GitBranch, render: () => <RoutingSection or={or} /> },
    { id: 'constraints', no: 6, title: 'Constraints', icon: ShieldCheck, render: () => <ConstraintsSection or={or} /> },
    { id: 'risk', no: 7, title: 'Safety & Risk', icon: Gauge, render: () => <RiskSection or={or} /> },
    { id: 'agents', no: 8, title: 'Agent Findings', icon: Cpu, render: () => <AgentFindingsSection or={or} /> },
    { id: 'evidence', no: 9, title: 'Evidence & Sources', icon: Database, render: () => <EvidenceSection or={or} /> },
    { id: 'decision', no: 10, title: 'Final Decision', icon: ClipboardCheck, render: () => <DecisionSection or={or} /> },
  ]
  const available = sections
    .map((s) => ({ ...s, body: s.render() }))
    .filter((s) => s.body !== null)
  const current = available.find((s) => s.id === active) ?? available[0]
  const curIdx = available.findIndex((s) => s.id === current.id)
  const goto = (delta: number) => {
    setActive(available[(curIdx + delta + available.length) % available.length].id)
  }

  return (
    <div className="space-y-6">
      {/* Grounding note */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
        <Database className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <p className="text-xs text-blue-700 leading-relaxed">
          {or.grounding || 'This report is derived entirely from actual workflow outputs. No schedule, delay, constraint, route, risk value or reason is invented.'}
        </p>
      </div>

      {/* Section navigation */}
      <div className="bg-white rounded-lg border border-gray-200 p-2">
        <div className="flex flex-wrap gap-1.5">
          {available.map((s) => {
            const isActive = s.id === current.id
            const Icon = s.icon
            return (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] font-semibold transition-colors ${
                  isActive
                    ? 'bg-railway-accent text-white border-railway-accent'
                    : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                }`}
              >
                <span className={`w-4 h-4 rounded border flex items-center justify-center text-[9px] font-bold ${
                  isActive ? 'bg-white/20 border-white/30 text-white' : 'bg-white border-gray-200 text-gray-400'
                }`}>
                  {s.no}
                </span>
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                <span className="hidden md:inline">{s.title}</span>
                <span className="md:hidden">{s.title.split(' ')[0]}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Active section */}
      {current.body}

      {/* Section paging */}
      <div className="flex items-center justify-between bg-white rounded-lg border border-gray-200 p-3">
        <button
          onClick={() => goto(-1)}
          disabled={available.length <= 1}
          className="inline-flex items-center gap-1 text-xs font-semibold text-gray-600 hover:text-railway-accent disabled:opacity-40 disabled:hover:text-gray-600"
        >
          <ArrowRight className="w-3.5 h-3.5 rotate-180" /> Previous
        </button>
        <span className="text-[11px] text-gray-400 font-mono">Section {curIdx + 1} of {available.length}</span>
        <button
          onClick={() => goto(1)}
          disabled={available.length <= 1}
          className="inline-flex items-center gap-1 text-xs font-semibold text-gray-600 hover:text-railway-accent disabled:opacity-40 disabled:hover:text-gray-600"
        >
          Next <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Approve / Reject actions */}
      {readOnly ? (
        <div className="flex flex-col gap-3 bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <ClipboardCheck className="w-4 h-4 text-gray-400" />
            <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
              Application Status
            </h3>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={plan?.status || 'GENERATED'} />
            <span className="text-xs text-gray-600 leading-relaxed">
              {plan?.status === 'PENDING_REVIEW'
                ? 'This plan is awaiting the officer for approval or rejection.'
                : plan?.status === 'APPROVED' || plan?.status === 'PUBLISHED'
                  ? 'This plan has been approved and published.'
                  : plan?.status === 'REJECTED'
                    ? 'This plan was rejected; a revised plan may be in progress.'
                    : 'Track the plan status above as it moves through the workflow.'}
            </span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3 bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <ClipboardCheck className="w-4 h-4 text-emerald-600" />
            <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
              Officer Action Required
            </h3>
          </div>
          <div className="flex gap-4">
            <button
              onClick={onApprove}
              disabled={approving || !canDecide}
              className="flex-1 bg-green-600 text-white py-3 rounded-md hover:bg-green-700 transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              {approving ? 'Publishing...' : 'Approve & Publish'}
            </button>
            <button
              onClick={onReject}
              disabled={!canDecide}
              className="flex-1 bg-red-600 text-white py-3 rounded-md hover:bg-red-700 transition-colors font-medium disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <XCircle className="w-4 h-4" />
              Reject & Trigger Replanning
            </button>
          </div>
          {!canDecide && (
            <p className="text-[11px] text-gray-500">
              This plan is no longer in PENDING_REVIEW; decisions for this version are closed.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/* ----------------------------------------------------------------------- */

function SectionCard({ no, title, icon: Icon, children, tone }: {
  no: number
  title: string
  icon: any
  tone?: string
  children: React.ReactNode
}) {
  const badge = tone === 'green' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : tone === 'red' ? 'bg-red-50 text-red-700 border-red-200'
    : tone === 'amber' ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-blue-50 text-blue-700 border-blue-200'
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className={`w-6 h-6 rounded-md border flex items-center justify-center text-[11px] font-bold ${badge}`}>
          {no}
        </span>
        <Icon className="w-4 h-4 text-gray-400" />
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
          {title}
        </h3>
      </div>
      {children}
    </div>
  )
}

function StatusChip({ label, kind }: { label: string; kind: 'green' | 'red' | 'amber' | 'gray' }) {
  const cls = kind === 'green' ? 'bg-green-50 text-green-700 border-green-200'
    : kind === 'red' ? 'bg-red-50 text-red-700 border-red-200'
    : kind === 'amber' ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-gray-50 text-gray-500 border-gray-200'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-bold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

function Bar({ value, label }: { value: number | null | undefined; label?: string }) {
  if (value == null) return <p className="text-xs text-gray-500 font-mono">{label || '—'}</p>
  const capped = Math.min(100, Math.max(0, Number(value)))
  const color = capped > 60 ? '#B3261E' : capped > 35 ? '#A15C00' : '#18794E'
  return (
    <div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${capped}%`, background: color }} />
      </div>
      <p className="text-[11px] font-mono text-gray-500 mt-1">{capped}</p>
    </div>
  )
}

function Metric({ k, v }: { k: string; v: any }) {
  if (v === undefined || v === null || v === '' || v === false) return null
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-50 py-1 last:border-0">
      <span className="text-[11px] text-gray-500 capitalize">{k.replace(/_/g, ' ')}</span>
      <span className="text-xs text-gray-700 font-medium text-right">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
    </div>
  )
}

/* ---- 1 Executive Recommendation ---------------------------------------- */

function ExecSection({ or }: { or: OfficerReportData }) {
  const ex = or.executive || {}
  const rec = String(ex.recommendation || 'REVIEW').toUpperCase()
  const recTone = rec === 'APPROVE' ? 'green' : rec === 'REJECT' ? 'red' : 'amber'
  const recText = rec === 'APPROVE' ? 'APPROVE' : rec === 'REJECT' ? 'REJECT' : 'REVIEW'
  const metrics: [string, any, any][] = [
    ['Block', ex.block_window ? `${ex.block_window}` : '—', Clock],
    ['Date', ex.date || '—', Timer],
    ['Section', ex.section || '—', GitBranch],
    ['Track / Line', ex.track_no || '—', Layers],
    ['Duration', ex.duration_minutes != null ? `${ex.duration_minutes} min` : '—', Timer],
    ['Affected trains', `${ex.affected_trains ?? '—'}`, TrainFront],
    ['Total delay', ex.total_delay_minutes != null ? `${ex.total_delay_minutes} min` : '—', TrendingUp],
    ['Max delay', ex.max_delay_minutes != null ? `${ex.max_delay_minutes} min` : '—', AlertTriangle],
    ['Rerouted / held', `${ex.rerouted ?? '—'} / ${ex.held ?? '—'}`, Layers],
    ['Risk score', ex.risk_score != null ? `${ex.risk_score}/100` : '—', Gauge],
    ['Confidence', ex.confidence != null ? `${ex.confidence}%` : '—', Gauge],
    ['Solver', ex.solver_status || '—', Cpu],
  ]
  return (
    <SectionCard no={1} title="Executive Recommendation" icon={FileText} tone={rec === 'APPROVE' ? 'green' : rec === 'REJECT' ? 'red' : 'amber'}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <StatusChip label={`RECOMMENDATION: ${recText}`} kind={recTone as any} />
        <RiskBadge level={ex.risk_level || 'LOW'} />
        {ex.auto_replanned && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-amber-200 bg-amber-50 text-[10px] font-bold text-amber-700 uppercase tracking-wide">
            <Lightbulb className="w-3 h-3" /> Auto-replanned ×{ex.retry_count || 0}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {metrics.map(([k, v, Icon]) => (
          <div key={k as string} className="rounded-md bg-gray-50 border border-gray-100 p-3">
            <Icon className="w-3.5 h-3.5 text-gray-400 mb-1.5" />
            <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">{k}</p>
            <p className="text-sm font-mono font-bold text-gray-900 mt-0.5">{v}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

/* ---- 2 Why This Block Was Selected -------------------------------------- */

function WhySection({ or }: { or: OfficerReportData }) {
  const rationale = or.selection_rationale
  if (!rationale) return null
  return (
    <SectionCard no={2} title="Why This Block Was Selected" icon={Lightbulb} tone="green">
      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">
            Reasons (from workflow outputs)
          </p>
          <ul className="space-y-1.5">
            {(rationale.reasons || []).map((r, i) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" /> {r}
              </li>
            ))}
            {(!rationale.reasons || rationale.reasons.length === 0) && (
              <li className="text-xs text-gray-500">No rationale recorded.</li>
            )}
          </ul>
          <p className="text-[11px] text-gray-500 mt-3">
            Preferred window: {rationale.preferred_window || '—'} ·{' '}
            {rationale.alternative_windows_considered ?? 0} alternative windows evaluated.
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">
            Trade-offs & Considerations
          </p>
          <ul className="space-y-1.5">
            {(rationale.tradeoffs || []).map((t, i) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed">
                <span className="text-amber-600 mt-0.5">⚖</span> {t}
              </li>
            ))}
            {(!rationale.tradeoffs || rationale.tradeoffs.length === 0) && (
              <li className="text-xs text-gray-500">No adverse trade-offs flagged by the analysis.</li>
            )}
          </ul>
        </div>
      </div>
    </SectionCard>
  )
}

/* ---- 3 Train-by-Train Impact -------------------------------------------- */

function TrainImpactSection({ or }: { or: OfficerReportData }) {
  const rows = or.train_impact || []
  return (
    <SectionCard no={3} title="Train-by-Train Impact" icon={TrainFront} tone="amber">
      {rows.length === 0 ? (
        <p className="text-xs text-gray-500">No trains affect the recommended window in the timetable simulation.</p>
      ) : (
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full text-left text-xs min-w-[720px]">
            <thead>
              <tr className="text-gray-400 text-[10px] uppercase tracking-wider border-b border-gray-100">
                <th className="py-2 pr-3">Train</th>
                <th className="py-2 pr-3">Priority</th>
                <th className="py-2 pr-3">Scheduled</th>
                <th className="py-2 pr-3">Delay</th>
                <th className="py-2 pr-3">Action</th>
                <th className="py-2 pr-3">Regulation</th>
                <th className="py-2 pr-3">Explanation</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2.5 pr-3 font-bold text-gray-900 font-mono">
                    {r.train_number} <span className="text-gray-400 font-normal">{r.train_name}</span>
                  </td>
                  <td className="py-2.5 pr-3 text-gray-500">{r.priority || '—'}</td>
                  <td className="py-2.5 pr-3 font-mono text-gray-600">
                    {r.scheduled_arrival || '—'} – {r.scheduled_departure || '—'}
                  </td>
                  <td className="py-2.5 pr-3">
                    <span className={`inline-flex px-1.5 py-0.5 rounded-md border text-[10px] font-bold ${
                      Number(r.delay_minutes) > 30 ? 'bg-red-50 text-red-700 border-red-200'
                      : Number(r.delay_minutes) > 0 ? 'bg-amber-50 text-amber-700 border-amber-200'
                      : 'bg-green-50 text-green-700 border-green-200'
                    }`}>
                      +{Number(r.delay_minutes ?? 0).toFixed(1)} min
                    </span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <StatusChip label={r.action || 'DELAY'} kind={String(r.action).toUpperCase() === 'REROUTE' ? 'red' : String(r.action).toUpperCase() === 'HOLD' ? 'amber' : 'gray'} />
                  </td>
                  <td className="py-2.5 pr-3 text-gray-600">{r.regulation || 'NORMAL'}</td>
                  <td className="py-2.5 pr-3 text-gray-500 leading-snug max-w-[260px]">{r.explanation || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

/* ---- 4 Alternative Windows ---------------------------------------------- */

function AltWindowsSection({ or }: { or: OfficerReportData }) {
  const rows = or.alternative_windows || []
  if (rows.length === 0) return null
  return (
    <SectionCard no={4} title="Alternative Windows Evaluated" icon={Clock} tone="blue">
      <div className="overflow-x-auto -mx-1 px-1">
        <table className="w-full text-left text-xs min-w-[680px]">
          <thead>
            <tr className="text-gray-400 text-[10px] uppercase tracking-wider border-b border-gray-100">
              <th className="py-2 pr-3">Window</th>
              <th className="py-2 pr-3">Trains</th>
              <th className="py-2 pr-3">Est. delay</th>
              <th className="py-2 pr-3">Score</th>
              <th className="py-2 pr-3">Preferred</th>
              <th className="py-2 pr-3">Verdict</th>
              <th className="py-2 pr-3">Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-gray-50 align-top">
                <td className="py-2.5 pr-3 font-mono font-bold text-gray-900">{r.window || '—'}</td>
                <td className="py-2.5 pr-3 text-gray-500">{r.affected_trains ?? '—'}</td>
                <td className="py-2.5 pr-3 text-gray-500">{r.estimated_delay_minutes ?? 0} min</td>
                <td className="py-2.5 pr-3 font-mono text-gray-600">{Number(r.score ?? 0).toFixed(2)}</td>
                <td className="py-2.5 pr-3 text-gray-500">{r.within_preferred ? 'Yes' : 'No'}</td>
                <td className="py-2.5 pr-3">
                  <StatusChip label={r.verdict || '—'} kind={r.verdict === 'SELECTED' ? 'green' : 'red'} />
                </td>
                <td className="py-2.5 pr-3 text-gray-500 leading-snug">
                  {(r.basis || []).map((b, j) => (
                    <p key={j} className={j > 0 ? 'mt-1' : ''}>• {b}</p>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}

/* ---- 5 Alternative Routing / Regulation ---------------------------------- */

function RoutingSection({ or }: { or: OfficerReportData }) {
  const rows = or.routing_alternatives || []
  return (
    <SectionCard no={5} title="Alternative Routing & Regulation" icon={GitBranch} tone="blue">
      {rows.length === 0 ? (
        <p className="text-xs text-gray-500">No affected trains, so no routing or regulation alternatives were required.</p>
      ) : (
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full text-left text-xs min-w-[640px]">
            <thead>
              <tr className="text-gray-400 text-[10px] uppercase tracking-wider border-b border-gray-100">
                <th className="py-2 pr-3">Train</th>
                <th className="py-2 pr-3">Proposed</th>
                <th className="py-2 pr-3">Decided</th>
                <th className="py-2 pr-3">Feasible</th>
                <th className="py-2 pr-3">Add. delay</th>
                <th className="py-2 pr-3">Note / reasoning</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-gray-50 align-top">
                  <td className="py-2.5 pr-3 font-mono font-bold text-gray-900">{r.train_number}</td>
                  <td className="py-2.5 pr-3">
                    <StatusChip label={r.proposed_action || 'NORMAL'} kind="gray" />
                    {r.proposed_reasoning && <p className="text-[11px] text-gray-500 mt-1">{r.proposed_reasoning}</p>}
                  </td>
                  <td className="py-2.5 pr-3">
                    <StatusChip label={r.decided_action || 'NORMAL'} kind={r.decided_action === 'DIVERT' ? 'red' : r.decided_action === 'HOLD' ? 'amber' : 'green'} />
                  </td>
                  <td className="py-2.5 pr-3 text-gray-500">{r.feasible ? 'Yes' : 'No'}</td>
                  <td className="py-2.5 pr-3 font-mono text-gray-600">+{Number(r.additional_delay ?? 0).toFixed(1)} min</td>
                  <td className="py-2.5 pr-3 text-gray-500 leading-snug">{r.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

/* ---- 6 Constraints Considered --------------------------------------------- */

function ConstraintsSection({ or }: { or: OfficerReportData }) {
  const c = or.constraints
  if (!c) return null
  const GroupBlock = ({ label, items, tone, Icon, empty }: {
    label: string
    items: { rule?: string; detail?: string }[]
    tone: 'green' | 'red' | 'amber'
    Icon: any
    empty: string
  }) => (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-3.5 h-3.5 text-gray-400" />
        <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold">{label}</p>
        <span className="ml-auto text-[10px] font-mono text-gray-400">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-gray-500">{empty}</p>
      ) : (
        <div className="space-y-1.5">
          {items.map((it, i) => (
            <div key={i} className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
              <div className="flex items-center gap-2">
                {tone === 'red' ? <XCircle className="w-3 h-3 text-red-500 shrink-0" />
                  : tone === 'amber' ? <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
                  : <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />}
                <p className="text-xs font-semibold text-gray-900">{it.rule || 'rule'}</p>
              </div>
              {it.detail && <p className="text-[11px] text-gray-500 mt-1 pl-5">{it.detail}</p>}
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center gap-2">
        <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400">Overall</p>
        <StatusChip label={c.valid ? 'SATISFIED' : 'NOT SATISFIED'} kind={c.valid ? 'green' : 'red'} />
      </div>
    </div>
  )

  return (
    <SectionCard no={6} title="Constraints Considered" icon={ShieldCheck} tone={c.valid ? 'green' : 'red'}>
      <div className="grid md:grid-cols-3 gap-5">
        <GroupBlock label="Satisfied" items={c.satisfied || []} tone="green" Icon={CheckCircle2} empty="No constraint checks recorded." />
        <GroupBlock label="Warnings" items={c.warnings || []} tone="amber" Icon={AlertTriangle} empty="No warnings." />
        <GroupBlock label="Violations" items={c.violations || []} tone="red" Icon={XCircle} empty="No violations." />
      </div>
    </SectionCard>
  )
}

/* ---- 7 Safety & Risk Explanation ------------------------------------------ */

function RiskSection({ or }: { or: OfficerReportData }) {
  const risk = or.risk
  if (!risk) return null
  const cats = risk.categories || []
  return (
    <SectionCard no={7} title="Safety & Risk Explanation" icon={ShieldCheck} tone={Number(risk.overall_score) > 60 ? 'red' : Number(risk.overall_score) > 35 ? 'amber' : 'green'}>
      <div className="flex items-center gap-3 mb-4">
        <p className="text-sm font-bold text-gray-900">Overall risk: {risk.risk_level || '—'}</p>
        <span className="font-mono text-xs text-gray-500">({Number(risk.overall_score ?? 0)}/100)</span>
      </div>
      <div className="grid md:grid-cols-2 gap-3 mb-4">
        {cats.map((cat, i) => (
          <div key={i} className="rounded-md border border-gray-100 bg-gray-50 p-3">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <p className="text-xs font-bold text-gray-900">{cat.type}</p>
              <StatusChip label={cat.status || '—'} kind={cat.status === 'PASS' ? 'green' : cat.status === 'VIOLATION' || cat.status === 'NON_COMPLIANT' ? 'red' : 'amber'} />
            </div>
            <div className="mb-2">
              <Bar value={cat.score} label={cat.status || ''} />
            </div>
            <p className="text-[11px] text-gray-500 leading-snug mb-1"><span className="font-semibold text-gray-600">Cause:</span> {cat.basis || '—'}</p>
            <p className="text-[11px] text-gray-500 leading-snug"><span className="font-semibold text-gray-600">Mitigation:</span> {cat.mitigation || '—'}</p>
          </div>
        ))}
      </div>
      {(risk.warnings?.length || risk.mitigations?.length) ? (
        <div className="grid md:grid-cols-2 gap-5 border-t border-gray-100 pt-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Warnings</p>
            <ul className="space-y-1.5">
              {(risk.warnings || []).map((w, i) => (
                <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />{w}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Mitigations</p>
            <ul className="space-y-1.5">
              {(risk.mitigations || []).map((m, i) => (
                <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />{m}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </SectionCard>
  )
}

/* ---- 8 AI Agent Findings --------------------------------------------------- */

function AgentFindingsSection({ or }: { or: OfficerReportData }) {
  const findings = or.agent_findings || []
  if (findings.length === 0) return null
  return (
    <SectionCard no={8} title="AI Agent Findings" icon={Cpu} tone="blue">
      <div className="grid gap-3">
        {findings.map((f, i) => (
          <div key={i} className="rounded-md border border-gray-100 bg-gray-50 p-3">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-xs font-bold text-gray-900">{f.role || f.agent}</span>
              <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{f.agent}</span>
            </div>
            {f.summary && <p className="text-[11px] text-gray-600 leading-snug mb-1.5">{f.summary}</p>}
            {f.metrics && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 mt-1">
                {Object.entries(f.metrics).map(([k, v]) => <Metric key={k} k={k} v={v} />)}
              </div>
            )}
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

/* ---- 9 Evidence & Sources --------------------------------------------------- */

function EvidenceSection({ or }: { or: OfficerReportData }) {
  const groups = or.evidence_sources || []
  if (groups.length === 0) return null
  const iconFor = (source: string) => {
    const s = (source || '').toLowerCase()
    if (s.includes('timetable') || s.includes('simulation')) return FlaskConical
    if (s.includes('cp-sat')) return Cpu
    if (s.includes('rag')) return BookOpen
    if (s.includes('historical')) return History
    if (s.includes('tavily') || s.includes('web')) return Globe
    return Activity
  }
  const toneFor = (tag?: string) => tag === 'FACT' ? 'green' : tag === 'CALCULATION' ? 'amber' : 'blue'
  return (
    <SectionCard no={9} title="Evidence & Sources" icon={Database} tone="green">
      <div className="grid md:grid-cols-2 gap-3">
        {groups.map((g, i) => {
          const Icon = iconFor(g.source || '')
          const tone = toneFor(g.tag) as any
          return (
            <div key={i} className="rounded-md border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <Icon className="w-3.5 h-3.5 text-gray-400" />
                <p className="text-xs font-bold text-gray-900">{g.source}</p>
                <span className={`ml-auto inline-flex px-1.5 py-0.5 rounded-md border text-[9px] font-bold uppercase tracking-wide ${
                  tone === 'green' ? 'bg-green-50 text-green-700 border-green-200'
                  : tone === 'amber' ? 'bg-amber-50 text-amber-700 border-amber-200'
                  : 'bg-blue-50 text-blue-700 border-blue-200'
                }`}>{g.tag || '—'}</span>
              </div>
              {g.detail && <p className="text-[11px] text-gray-600 leading-snug mb-1.5">{g.detail}</p>}
              {(g.items?.length || 0) > 0 && (
                <ul className="space-y-0.5 mt-1">
                  {(g.items || []).slice(0, 6).map((it, j) => (
                    <li key={j} className="text-[11px] text-gray-500 leading-snug">• {it}</li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
      <p className="text-[10px] text-gray-400 mt-3 flex items-center gap-1.5">
        <Sparkles className="w-3 h-3" />
        FACT = timetable/simulation/rules · CALCULATION = CP-SAT & derived figures · AI RECOMMENDATION = LLM proposals (evidence only, never authoritative).
      </p>
    </SectionCard>
  )
}

/* ---- 10 Final Decision ------------------------------------------------------ */

function DecisionSection({ or }: { or: OfficerReportData }) {
  const fd = or.final_decision
  if (!fd) return null
  return (
    <SectionCard no={10} title="Final Decision Explanation" icon={ClipboardCheck} tone="green">
      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Benefits of this block</p>
          <ul className="space-y-1.5">
            {(fd.benefits || []).map((b, i) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />{b}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Residual risks</p>
          <ul className="space-y-1.5">
            {(fd.residual_risks || []).map((r, i) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />{r}</li>
            ))}
            {(!fd.residual_risks || fd.residual_risks.length === 0) && (
              <li className="text-xs text-gray-500">No residual risks flagged.</li>
            )}
          </ul>
        </div>
      </div>
      {(fd.mitigations?.length || fd.conditions?.length) ? (
        <div className="grid md:grid-cols-2 gap-5 border-t border-gray-100 pt-4 mt-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Mitigations</p>
            <ul className="space-y-1.5">
              {(fd.mitigations || []).map((m, i) => (
                <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />{m}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Conditions before execution</p>
            <ul className="space-y-1.5">
              {(fd.conditions || []).map((c, i) => (
                <li key={i} className="text-xs text-gray-700 flex gap-2 leading-relaxed"><ArrowRight className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />{c}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
      <div className="mt-4 rounded-md border border-gray-100 bg-gray-50 p-3 flex items-start gap-2">
        <Sparkles className="w-4 h-4 text-violet-500 shrink-0 mt-0.5" />
        <p className="text-[11px] text-gray-600 leading-relaxed">
          <span className="font-semibold text-gray-800">AI advisory: {fd.advisory || 'REVIEW'}</span> · Final authority:{' '}
          {fd.authority || 'OFFICER'}. {fd.weight_of_evidence || 'The AI explains workflow outputs and never changes them.'}
        </p>
      </div>
    </SectionCard>
  )
}

/* ---- Legacy fallback (plans generated before the enriched report) ---------- */

function LegacyReport({ rd, plan }: { rd?: ReportData; plan?: BlockPlan }) {
  const why = rd?.why_this_window || []
  const risks = rd?.risk as any
  const sc = rd?.safety_compliance as any
  const mitigations = rd?.risk_management_plan || []
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
      <p className="text-xs font-semibold text-amber-800 mb-1">
        Structured 10-section justification not available for this plan version.
      </p>
      <p className="text-[11px] text-amber-700">This plan was generated before the enriched officer report; a summary is shown instead.</p>

      {(why.length > 0 || plan) && (
        <div className="mt-3 bg-white rounded-md border border-amber-200 p-4">
          <h4 className="font-semibold text-gray-900 text-xs uppercase tracking-wide mb-2">Why this window</h4>
          <ul className="space-y-1.5">
            {why.map((w, i) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2">
                <span className="text-railway-accent">•</span>{w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(risks?.mitigations?.length || mitigations.length > 0) && (
        <div className="mt-3 bg-white rounded-md border border-amber-200 p-4">
          <h4 className="font-semibold text-gray-900 text-xs uppercase tracking-wide mb-2">Mitigation plan</h4>
          <ul className="space-y-1.5">
            {(risks?.mitigations || mitigations.map((m) => m.mitigation)).map((m: string, i: number) => (
              <li key={i} className="text-xs text-gray-700 flex gap-2"><span className="text-emerald-600">🛡</span>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {sc && (
        <div className="mt-3 bg-white rounded-md border border-amber-200 p-4">
          <h4 className="font-semibold text-gray-900 text-xs uppercase tracking-wide mb-2">Compliance</h4>
          <p className="text-xs text-gray-600">{sc.passed ? 'Compliance checks passed.' : 'Compliance issues found.'}</p>
        </div>
      )}
    </div>
  )
}