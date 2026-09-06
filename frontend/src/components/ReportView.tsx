import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, ArrowLeft, Briefcase, Cpu, Database, ExternalLink,
  FileText, Fingerprint, Gauge, Globe, History, Layers, Lock, ShieldCheck,
  Sparkles, Timer, TrainFront, TrendingUp,
} from 'lucide-react'
import type { Report, ReportData, AgentResult, WebSource, ImpactRow } from '../types'
import { PriorityBadge, RiskBadge } from './StatusBadge'
import AgentGraph, { type StepRow } from './AgentGraph'

const TABS = [
  { id: 'overview', label: 'Overview', icon: FileText },
  { id: 'context', label: 'Context', icon: Briefcase },
  { id: 'reasoning', label: 'Reasoning', icon: Cpu },
  { id: 'evidence', label: 'Evidence', icon: Database },
  { id: 'impact', label: 'Impact', icon: TrainFront },
  { id: 'optimize', label: 'Optimization & Compliance', icon: ShieldCheck },
  { id: 'trace', label: 'Trace', icon: Activity },
] as const

type TabId = (typeof TABS)[number]['id']

export default function ReportView({ report, requestData, onBack }: {
  report: Report
  requestData?: { id: number } | null
  onBack?: () => void
}) {
  const [tab, setTab] = useState<TabId>('overview')
  const [showGraph, setShowGraph] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const rd = report.plan?.report_data as ReportData | undefined
  const plan = report.plan

  const stepRows: StepRow[] = useMemo(() => {
    const map: Record<string, string> = {
      data_validation: 'validate', maintenance_agent: 'maintenance', traffic_agent: 'traffic',
      priority_agent: 'priority', merge: 'merge', historical_agent: 'historical',
      rag_retrieval: 'rag', web_research: 'web_research', evidence_validation: 'evidence',
      candidate_generation: 'candidate', cp_sat_optimization: 'optimize', simulation: 'simulate',
      routing: 'routing', route_optimization: 'route_optimize', gate: 'gate',
      constraint_validation: 'validate_constraints', risk: 'risk', decision_fusion: 'fusion',
      report_generation: 'report',
    }
    return (report.agent_results || []).map(a => ({
      agent: map[a.agent_name] || a.agent_name,
      status: a.status,
      data: a.output_data,
    }))
  }, [report])

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      {/* classified header */}
      <ClassifiedHeader rd={rd} plan={plan} requestData={requestData} onBack={onBack} />

      {/* tabs */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 -mx-1 px-1">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`tab-rail flex items-center gap-1.5 shrink-0 ${
              tab === t.id ? 'active' : ''
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
        <button
          onClick={() => setShowGraph(v => !v)}
          className="ml-auto tab-rail shrink-0 flex items-center gap-1.5"
          style={{ opacity: showGraph ? 1 : 0.7 }}
        >
          <Activity className="w-3.5 h-3.5" />
          Agent Graph
        </button>
      </div>

      {showGraph && (
        <div className="glass-deep rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <p className="h-overline">LANGRAPH TOPOLOGY — USE CASE RUNS</p>
            <Legend />
          </div>
          <AgentGraph steps={stepRows} failed={plan.status === 'FAILED'} selected={selected} onSelect={setSelected} />
          {selected && (
            <div className="mt-3 p-3 rounded-xl bg-white border border-so-line2 text-xs text-so-text">
              Node <span className="font-bold text-so-cyan">{selected}</span> — step detail in Trace tab below.
            </div>
          )}
        </div>
      )}

      {tab === 'overview' && <OverviewTab rd={rd} plan={plan} />}
      {tab === 'context' && <ContextTab rd={rd} />}
      {tab === 'reasoning' && <ReasoningTab rd={rd} />}
      {tab === 'evidence' && <EvidenceTab rd={rd} />}
      {tab === 'impact' && <ImpactTab rd={rd} />}
      {tab === 'optimize' && <OptimizeTab rd={rd} plan={plan} />}
      {tab === 'trace' && <TraceTab rd={rd} report={report} />}
    </motion.div>
  )
}

function ClassifiedHeader({ rd, plan, requestData, onBack }: {
  rd?: ReportData
  plan?: Report['plan']
  requestData?: { id: number } | null
  onBack?: () => void
}) {
  const advisory = rd?.ai_advisory
  const label: string = advisory?.label || 'RECOMMEND_REVIEW'
  const tone = label.includes('APPROVE') ? 'green' : label.includes('REJECT') ? 'red' : 'amber'
  const toneText = tone === 'green' ? 'text-so-green border-so-green/40 bg-so-green/10'
    : tone === 'red' ? 'text-so-red border-so-red/40 bg-so-red/10'
    : 'text-so-amber border-so-amber/40 bg-so-amber/10'

  return (
    <div className="glass rounded-2xl overflow-hidden border border-so-line2">
      <div className="h-0.5 bg-so-cyan" />
      <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-so-cyan/15 border border-so-cyan/30 flex items-center justify-center">
            <Fingerprint className="w-5 h-5 text-so-cyan" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="h-overline text-so-dim">CLASSIFIED · AI DISPOSITION REPORT</span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-so-text leading-tight">
              Block Plan V{plan?.version || 1} · {rd?.request_summary?.maintenance_type || 'Maintenance'} — {rd?.request_summary?.section || ''}
            </h2>
            <p className="text-xs text-so-dim mt-0.5">
              MR-{String(requestData?.id || rd?.request_summary?.id || '').padStart(5, '0')}
              {requestData?.id ? ` · Request ${requestData.id}` : ''} · Generated {rd?.generated_at ? new Date(rd.generated_at).toLocaleString() : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {requestData && <PriorityBadge priority={(rd?.request_summary?.priority as string) || 'low'} />}
          <span className={`chip border ${toneText}`}>
            <Sparkles className="w-3 h-3" /> AI: {label}
          </span>
          <RiskBadge level={(rd?.risk?.risk_level as string) || 'LOW'} />
          {onBack && (
            <button onClick={onBack} className="btn-ghost flex items-center gap-1.5 text-xs">
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
          )}
        </div>
      </div>
      {advisory?.is_final === false && (
        <div className="border-t border-so-line px-5 py-3 flex items-start gap-2.5 bg-so-amber/5">
          <AlertTriangle className="w-4 h-4 text-so-amber shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-so-amber">Advisory — not a sanction. Final authority: {advisory.approval_authority || 'Officer-in-charge'}.</p>
            {advisory.note && <p className="text-[11px] text-so-dim mt-0.5">{advisory.note}</p>}
          </div>
        </div>
      )}
    </div>
  )
}

function OverviewTab({ rd, plan }: { rd?: ReportData; plan?: Report['plan'] }) {
  const risk = rd?.risk
  const riskPct = Math.min(100, Number(risk?.overall_score ?? 0))
  const riskColor = riskPct > 60 ? 'bg-so-red' : riskPct > 35 ? 'bg-so-amber' : 'bg-so-green'
  const advisory = rd?.ai_advisory
  const metrics = useMemo(() => [
    { label: 'Proposed Block', value: plan ? `${plan.start_time}−${plan.end_time}` : '—', icon: Timer },
    { label: 'Affected Trains', value: String(rd?.train_impact?.total_affected ?? plan?.affected_trains?.length ?? 0), icon: TrainFront },
    { label: 'Est. Delay', value: `${rd?.train_impact?.total_delay ?? plan?.estimated_delay_minutes ?? 0} min`, icon: TrendingUp },
    { label: 'Confidence', value: `${rd?.confidence ?? plan?.confidence ?? 0}%`, icon: Gauge },
  ], [rd, plan])

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map((m, i) => (
          <motion.div key={m.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="glass-deep rounded-2xl p-4">
            <m.icon className="w-4 h-4 text-so-cyan mb-2" />
            <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">{m.label}</p>
            <p className="text-lg font-extrabold text-so-text mt-0.5 font-mono">{m.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">WHY THIS WINDOW</p>
          <div className="flex items-baseline gap-2 mb-3">
            <span className="text-2xl font-extrabold text-so-cyan font-mono">
              {plan ? `${plan.start_time} − ${plan.end_time}` : '—'}
            </span>
            <span className="text-xs text-so-dim">{plan?.proposed_date || rd?.recommended_block?.date || ''}</span>
          </div>
          <ul className="space-y-2">
            {(rd?.why_this_window || []).map((w, i) => (
              <li key={i} className="flex gap-2 text-xs text-so-text leading-relaxed">
                <span className="text-so-cyan mt-0.5">◆</span> {w}
              </li>
            ))}
            {(!rd?.why_this_window || rd.why_this_window.length === 0) && (
              <li className="text-xs text-so-dim">No rationale recorded.</li>
            )}
          </ul>
        </div>

        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">RISK & CONFIDENCE</p>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs text-so-dim font-medium">Overall risk</p>
            <p className="text-sm font-bold text-so-text">
              {risk?.risk_level || '—'} <span className="text-so-dim font-normal">({riskPct}/100)</span>
            </p>
          </div>
          <div className="h-2.5 rounded-full bg-so-panel overflow-hidden border border-so-line">
            <div className={`h-full ${riskColor} rounded-full transition-all`} style={{ width: `${riskPct}%` }} />
          </div>
          <div className="grid grid-cols-3 gap-2 mt-4">
            <MiniGauge label="Safety" value={Number(risk?.safety_score ?? 0)} />
            <MiniGauge label="Operational" value={Number(risk?.operational_score ?? 0)} />
            <MiniGauge label="Passenger" value={Number(risk?.passenger_score ?? 0)} />
          </div>
        </div>
      </div>

      {rd?.ai_explanation && (
        <div className="glass-deep rounded-2xl p-5 border-l-2 border-l-so-cyan">
          <p className="h-overline text-so-cyan mb-2">AI EXPLANATION</p>
          <p className="text-sm text-so-text leading-relaxed">{rd.ai_explanation}</p>
        </div>
      )}

      {advisory && (
        <div className="glass-deep rounded-2xl p-5 flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-so-violet shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-so-text">AI Advisory — {advisory.label || 'no recommendation'}</p>
            <p className="text-xs text-so-dim mt-1">{advisory.note || 'Decision Fusion synthesis is advisory only; deterministic constraint checks remain binding.'}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function ContextTab({ rd }: { rd?: ReportData }) {
  const ctx = rd?.request_context
  const cost = rd?.cost_estimate
  const sum = rd?.request_summary
  const weather = rd?.weather as any

  const rows: [string, any][] = [
    ['Department', sum?.department],
    ['Maintenance type', sum?.maintenance_type],
    ['Section', sum?.section],
    ['Location', sum?.location],
    ['Date', sum?.date],
    ['Duration', sum?.duration ? `${sum.duration} min` : '—'],
    ['Priority', sum?.priority],
    ['Work type', ctx?.work_type],
    ['Track', ctx?.track_no],
    ['Equipment', ctx?.equipment],
    ['Crew size', ctx?.crew_size],
    ['Weather sensitive', ctx?.weather_sensitive],
    ['Preferred window', ctx?.preferred_window],
    ['Special instructions', ctx?.special_instructions],
  ]

  return (
    <div className="space-y-5">
      <div className="glass-deep rounded-2xl p-5">
        <p className="h-overline mb-3">REQUEST PROFILE</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3">
          {rows.map(([k, v]) => (
            <div key={k}>
              <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">{k}</p>
              <p className="text-xs text-so-text mt-0.5 truncate">{v === null || v === undefined || v === '' ? '—' : stringify(v)}</p>
            </div>
          ))}
        </div>
      </div>

      {cost && (cost.material_cost || cost.crew_size) && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">COST ESTIMATE (DERIVED)</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">Material cost</p>
              <p className="text-sm font-bold text-so-text font-mono mt-0.5">
                {cost.currency || 'INR'} {cost.material_cost?.toLocaleString() ?? '—'}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">Crew size</p>
              <p className="text-sm font-bold text-so-text font-mono mt-0.5">{cost.crew_size ?? '—'}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">Est. crew hours</p>
              <p className="text-sm font-bold text-so-text font-mono mt-0.5">{cost.estimated_crew_hours ?? '—'} h</p>
            </div>
          </div>
          {cost.note && <p className="text-[11px] text-so-dim mt-3">{cost.note}</p>}
        </div>
      )}

      {weather && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">WEATHER CHECK</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <WeatherItem label="Condition" value={weather.condition} />
            <WeatherItem label="Temperature" value={weather.temperature_c != null ? `${weather.temperature_c}°C` : '—'} />
            <WeatherItem label="Precipitation" value={weather.precipitation_probability != null ? `${weather.precipitation_probability}%` : '—'} />
            <WeatherItem label="Wind" value={weather.wind_kmh != null ? `${weather.wind_kmh} km/h` : '—'} />
          </div>
        </div>
      )}
    </div>
  )
}

function ReasoningTab({ rd }: { rd?: ReportData }) {
  const adv = rd?.ai_advisory

  return (
    <div className="space-y-5">
      {rd?.ai_replanning?.auto_replanned && (
        <div className="rounded-2xl p-5 border border-so-amber/40 bg-so-amber/10 flex items-start gap-3">
          <Lock className="w-5 h-5 text-so-amber shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-so-amber">Auto re-plan before review</p>
            <p className="text-xs text-so-text mt-1">{rd.ai_replanning.note}</p>
            {rd.ai_replanning.avoid_windows?.length ? (
              <p className="text-[11px] text-so-dim mt-1">Avoided windows: {rd.ai_replanning.avoid_windows.join(', ')}</p>
            ) : null}
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">KEY FACTORS</p>
          <ul className="space-y-2">
            {(rd?.key_factors || []).map((f, i) => (
              <li key={i} className="flex gap-2 text-xs text-so-text leading-relaxed">
                <span className="text-so-cyan mt-0.5">▸</span> {f}
              </li>
            ))}
          </ul>
        </div>
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">TRADE-OFFS CONSIDERED</p>
          <ul className="space-y-2">
            {(rd?.tradeoffs || []).map((t, i) => (
              <li key={i} className="flex gap-2 text-xs text-so-text leading-relaxed">
                <span className="text-so-amber mt-0.5">⚖</span> {t}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {rd?.decision_evidence && <KvGrid title="DECISION EVIDENCE" data={rd.decision_evidence} />}
      {rd?.priority_analysis && <KvGrid title="PRIORITY ANALYSIS" data={rd.priority_analysis} />}

      {rd?.agent_assessments && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">AGENT ASSESSMENTS</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(rd.agent_assessments).map(([name, val]) => (
              <div key={name} className="rounded-xl bg-white border border-so-line p-4">
                <p className="text-xs font-bold text-so-text mb-1.5 capitalize">{name.replace(/_/g, ' ')}</p>
                <div className="space-y-1">
                  {typeof val === 'object' && val ? (
                    Object.entries(val as Record<string, any>).map(([k, v]) => {
                      if (v === undefined || v === null || v === '') return null
                      return (
                        <div key={k} className="text-[11px] text-so-dim">
                          <span className="capitalize">{k.replace(/_/g, ' ')}:</span>{' '}
                          <span className="text-so-text font-medium">{Array.isArray(v) ? v.join(', ') : stringify(v)}</span>
                        </div>
                      )
                    })
                  ) : (
                    <p className="text-[11px] text-so-text">{stringify(val)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {adv && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">FUSION DISPOSITION</p>
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-so-violet" />
            <div>
              <p className="text-sm font-bold text-so-text">{adv.label}</p>
              <p className="text-[11px] text-so-dim">{adv.approval_authority ? `Authority: ${adv.approval_authority}` : ''}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EvidenceTab({ rd }: { rd?: ReportData }) {
  const web = rd?.web_research_evidence || rd?.web_evidence
  const sources: WebSource[] = web?.sources || []
  const rag = rd?.rag_evidence
  const hist = rd?.historical_evidence

  return (
    <div className="space-y-5">
      {web && (
        <div className="glass-deep rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-1">
            <Globe className="w-4 h-4 text-so-cyan" />
            <p className="h-overline">WEB RESEARCH — LIVE EVIDENCE</p>
          </div>
          <p className="text-[11px] text-so-amber mb-4">{web.note || 'Evidence only — does not modify plan constraints.'}</p>
          {sources.length === 0 && <p className="text-xs text-so-dim">No sources captured (search unavailable or no results).</p>}
          <div className="grid md:grid-cols-2 gap-3">
            {sources.map((s, i) => (
              <a key={i} href={s.source_url || s.url} target="_blank" rel="noreferrer"
                className="block rounded-xl bg-white border border-so-line hover:border-so-cyan/40 transition-colors p-4 group">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[10px] font-mono text-so-dim">{s.domain || s.source_url?.split('/')[2] || 'web'}</span>
                  {s.authoritative && (
                    <span className="chip border bg-so-green/12 text-so-green border-so-green/35">authoritative</span>
                  )}
                  {s.relevance != null && (
                    <span className="chip border bg-so-cyan/10 text-so-cyan border-so-cyan/25">rel {s.relevance.toFixed(2)}</span>
                  )}
                  <ExternalLink className="w-3 h-3 text-so-dim group-hover:text-so-cyan ml-auto" />
                </div>
                {s.title && <p className="text-xs font-bold text-so-text leading-snug">{s.title}</p>}
                <p className="text-[11px] text-so-dim mt-1 leading-relaxed line-clamp-3">{s.snippet || s.content}</p>
              </a>
            ))}
          </div>
        </div>
      )}

      {rag && <KvGrid title="RAG RETRIEVAL — RAILWAY POLICY" data={rag} rich />}
      {hist && <KvGrid title="HISTORICAL EVIDENCE" data={hist} rich />}
    </div>
  )
}

function ImpactTab({ rd }: { rd?: ReportData }) {
  const ti = rd?.train_impact
  const rows: ImpactRow[] = rd?.impact_rows || []
  const rc = rd?.alternative_routing_considered

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Affected trains" value={String(ti?.total_affected ?? '0')} icon={TrainFront} tone="cyan" />
        <StatCard label="Total delay" value={`${ti?.total_delay ?? 0} min`} icon={TrendingUp} tone="amber" />
        <StatCard label="Max delay" value={`${ti?.max_delay ?? 0} min`} icon={AlertTriangle} tone="red" />
        <StatCard label="Rerouted / held" value={`${ti?.rerouted ?? 0} / ${ti?.held ?? 0}`} icon={Layers} tone="violet" />
      </div>

      <div className="glass-deep rounded-2xl p-5">
        <p className="h-overline mb-3">TRAIN IMPACT DETAIL</p>
        {rows.length === 0 ? (
          <p className="text-xs text-so-dim">No trains expected to be materially affected in the recommended window.</p>
        ) : (
          <div className="overflow-x-auto -mx-1 px-1">
            <table className="w-full text-left text-xs min-w-[640px]">
              <thead>
                <tr className="text-so-dim text-[10px] uppercase tracking-wider border-b border-so-line">
                  <th className="py-2 pr-3">Train</th>
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Sch. Arr</th>
                  <th className="py-2 pr-3">Sch. Dep</th>
                  <th className="py-2 pr-3">Proj. Arr</th>
                  <th className="py-2 pr-3">Delay</th>
                  <th className="py-2 pr-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-b border-so-line/60 hover:bg-gray-50">
                    <td className="py-2.5 pr-3 font-bold text-so-text font-mono">
                      {r.train_number} <span className="text-so-dim font-normal">{r.train_name}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-so-dim">{r.train_type}</td>
                    <td className="py-2.5 pr-3 font-mono text-so-text">{r.scheduled_arrival || r.arrival_time || '—'}</td>
                    <td className="py-2.5 pr-3 font-mono text-so-text">{r.scheduled_departure || r.departure_time || '—'}</td>
                    <td className="py-2.5 pr-3 font-mono">{r.projected_arrival || '—'}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`chip border ${Number(r.delay_minutes) > 30 ? 'bg-so-red/12 text-so-red border-so-red/35' : Number(r.delay_minutes) > 0 ? 'bg-so-amber/12 text-so-amber border-so-amber/35' : 'bg-so-green/12 text-so-green border-so-green/35'}`}>
                        +{r.delay_minutes ?? 0} min
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-so-dim capitalize">{r.action || r.impact || 'hold'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {rc && <KvGrid title="ALTERNATIVE ROUTING CONSIDERED" data={rc} />}
    </div>
  )
}

function OptimizeTab({ rd, plan }: { rd?: ReportData; plan?: Report['plan'] }) {
  const rb = rd?.recommended_block as any
  const opt = rd?.optimization as any
  const ro = rd?.route_optimization as any
  const sc = rd?.safety_compliance as any
  const risk = rd?.risk as any
  const mitigations = rd?.risk_management_plan || []

  return (
    <div className="space-y-5">
      {(rb || plan) && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">RECOMMENDED BLOCK</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Window" value={plan ? `${plan.start_time}−${plan.end_time}` : '—'} icon={Timer} tone="cyan" />
            <StatCard label="Score" value={rb?.score != null ? String(rb.score) : plan?.score != null ? String(plan.score) : '—'} icon={Gauge} tone="violet" />
            <StatCard label="Risk" value={plan?.risk_score != null ? String(plan.risk_score) : '—'} icon={AlertTriangle} tone="amber" />
            <StatCard label="Delay" value={`${plan?.estimated_delay_minutes ?? 0} min`} icon={TrendingUp} tone="red" />
          </div>
          <p className="text-xs text-so-dim mt-3">{rb?.rationale || rb?.reason || 'Recommended by deterministic optimization followed by compliance validation.'}</p>
        </div>
      )}

      {(opt || ro) && (
        <div className="grid md:grid-cols-2 gap-5">
          {opt && (
            <div className="glass-deep rounded-2xl p-5">
              <p className="h-overline mb-3">CP-SAT OPTIMIZATION</p>
              <MiniKeyVals data={opt} />
              {ro && (
                <>
                  <p className="h-overline mt-4 mb-2">ROUTE OPTIMIZER</p>
                  <MiniKeyVals data={ro} />
                </>
              )}
            </div>
          )}
        </div>
      )}

      {sc && (
        <div className="glass-deep rounded-2xl p-5 border-l-2 border-l-so-green">
          <p className="h-overline text-so-green mb-3">SAFETY & COMPLIANCE CHECK</p>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className={`chip border ${sc.passed ? 'bg-so-green/12 text-so-green border-so-green/35' : 'bg-so-red/12 text-so-red border-so-red/35'}`}>
              {sc.passed ? 'PASSED' : 'FAILED'}
            </span>
            <span className="text-xs text-so-dim">{String(sc.violations?.length || 0)} violations · {String(sc.warnings?.length || 0)} warnings</span>
          </div>
          {(sc.violations || []).map((v: any, i: number) => (
            <p key={i} className="text-[11px] text-so-red mb-1">✕ {stringify(v)}</p>
          ))}
          {(sc.warnings || []).map((w: any, i: number) => (
            <p key={i} className="text-[11px] text-so-amber mb-1">⚠ {stringify(w)}</p>
          ))}
          {(!sc.violations?.length && !sc.warnings?.length) && (
            <p className="text-xs text-so-dim">All hard constraints satisfied.</p>
          )}
        </div>
      )}

      {risk && <KvGrid title="RISK BREAKDOWN" data={pick(risk, ['overall', 'safety', 'operational', 'passenger'])} />}

      {mitigations.length > 0 && (
        <div className="glass-deep rounded-2xl p-5">
          <p className="h-overline mb-3">MITIGATION PLAN</p>
          <ul className="space-y-2">
            {mitigations.map((m, i) => (
              <li key={i} className="flex gap-2 text-xs text-so-text leading-relaxed">
                <ShieldCheck className="w-4 h-4 text-so-green shrink-0" /> {m.mitigation}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function TraceTab({ rd, report }: { rd?: ReportData; report: Report }) {
  const agents: AgentResult[] = report.agent_results || []
  return (
    <div className="space-y-5">
      <div className="glass-deep rounded-2xl p-5">
        <p className="h-overline mb-3">AGENT EXECUTION LOG</p>
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full text-left text-xs min-w-[560px]">
            <thead>
              <tr className="text-so-dim text-[10px] uppercase tracking-wider border-b border-so-line">
                <th className="py-2 pr-3">Step</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Summary</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a, i) => (
                <tr key={i} className="border-b border-so-line/60">
                  <td className="py-2 pr-3 font-mono text-so-text capitalize">{a.agent_name.replace(/_/g, ' ')}</td>
                  <td className="py-2 pr-3">
                    <span className={`chip border ${
                      a.status === 'completed' ? 'bg-so-green/12 text-so-green border-so-green/35'
                      : a.status === 'failed' ? 'bg-so-red/12 text-so-red border-so-red/35'
                      : 'bg-so-amber/12 text-so-amber border-so-amber/35'
                    }`}>{a.status}</span>
                  </td>
                  <td className="py-2 pr-3 text-so-dim line-clamp-2">{a.reasoning_summary || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {rd?.officer_feedback && (
        <div className="glass-deep rounded-2xl p-5 border-l-2 border-l-so-amber">
          <p className="h-overline text-so-amber mb-2">OFFICER FEEDBACK</p>
          <KvMini data={rd.officer_feedback} />
        </div>
      )}
    </div>
  )
}

/* ---------- primitives ---------- */

function Legend() {
  const items: [string, string][] = [
    ['#94A3B8', 'idle'], ['#1D5FA7', 'active'], ['#18794E', 'done'], ['#B3261E', 'failed'], ['#A15C00', 'loop retry'],
  ]
  return (
    <div className="flex items-center gap-4">
      {items.map(([c, l]) => (
        <span key={l} className="flex items-center gap-1.5 text-[10px] text-so-dim font-semibold uppercase tracking-wide">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} /> {l}
        </span>
      ))}
    </div>
  )
}

function StatCard({ label, value, icon: Icon, tone }: { label: string; value: string; icon: any; tone: string }) {
  const color: Record<string, string> = {
    cyan: 'text-so-cyan border-so-cyan/25 bg-so-cyan/10',
    amber: 'text-so-amber border-so-amber/25 bg-so-amber/10',
    red: 'text-so-red border-so-red/25 bg-so-red/10',
    violet: 'text-so-violet border-so-violet/25 bg-so-violet/10',
    green: 'text-so-green border-so-green/25 bg-so-green/10',
  }
  return (
    <div className="rounded-2xl bg-white border border-so-line p-4">
      <div className={`inline-flex w-7 h-7 rounded-lg border items-center justify-center mb-2 ${color[tone]}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">{label}</p>
      <p className="text-lg font-extrabold text-so-text font-mono mt-0.5">{value}</p>
    </div>
  )
}

function MiniGauge({ label, value }: { label: string; value: number }) {
  const capped = Math.min(100, Math.max(0, value))
  const color = capped > 60 ? 'bg-so-red' : capped > 35 ? 'bg-so-amber' : 'bg-so-green'
  return (
    <div className="rounded-xl bg-white border border-so-line p-3">
      <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold mb-1.5">{label}</p>
      <div className="h-1.5 rounded-full bg-so-panel overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${capped}%` }} />
      </div>
      <p className="text-xs font-bold text-so-text font-mono mt-1">{capped}</p>
    </div>
  )
}

function WeatherItem({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-white border border-so-line p-3">
      <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold">{label}</p>
      <p className="text-sm font-bold text-so-text mt-0.5">{value === null || value === undefined ? '—' : stringify(value)}</p>
    </div>
  )
}

function KvGrid({ title, data, rich }: { title: string; data: Record<string, any>; rich?: boolean }) {
  const entries = Object.entries(data || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return null
  return (
    <div className="glass-deep rounded-2xl p-5">
      <p className="h-overline mb-3">{title}</p>
      <div className="grid md:grid-cols-2 gap-3">
        {entries.slice(0, 16).map(([k, v]) => (
          <div key={k} className="rounded-xl bg-white border border-so-line p-3">
            <p className="text-[10px] uppercase tracking-wider text-so-dim font-semibold capitalize">{k.replace(/_/g, ' ')}</p>
            <p className="text-xs text-so-text mt-1 leading-relaxed break-words">{pretty(v, rich)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function MiniKeyVals({ data }: { data: Record<string, any> }) {
  const entries = Object.entries(data || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return (
    <div className="grid grid-cols-1 gap-1">
      {entries.slice(0, 12).map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-3 border-b border-so-line/40 py-1.5">
          <span className="text-[11px] text-so-dim capitalize">{k.replace(/_/g, ' ')}</span>
          <span className="text-xs text-so-text text-right">{Array.isArray(v) ? v.join(', ') : pretty(v)}</span>
        </div>
      ))}
    </div>
  )
}

function KvMini({ data }: { data: Record<string, any> }) {
  return (
    <div className="grid md:grid-cols-2 gap-2">
      {Object.entries(data || {}).map(([k, v]) => (
        <div key={k} className="text-xs">
          <span className="text-so-dim capitalize">{k.replace(/_/g, ' ')}: </span>
          <span className="text-so-text">{pretty(v)}</span>
        </div>
      ))}
    </div>
  )
}

function pick(obj: Record<string, any>, keys: string[]): Record<string, any> {
  const out: Record<string, any> = {}
  keys.forEach(k => { if (obj?.[k] !== undefined && obj?.[k] !== null) out[k] = obj[k] })
  return out
}

function pretty(v: any, rich?: boolean): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') {
    if (rich && Array.isArray(v) && v.every(x => typeof x === 'string')) return v.join(' · ')
    try { return JSON.stringify(v) } catch { return String(v) }
  }
  return String(v)
}

function stringify(v: any): string {
  return pretty(v)
}

void History
void Timer