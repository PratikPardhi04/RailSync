import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, Radio } from 'lucide-react'
import Layout from '../components/Layout'
import StatusBadge, { PriorityBadge } from '../components/StatusBadge'
import RejectModal from '../components/RejectModal'
import OfficerReport from '../components/OfficerReport'
import VersionHistory from '../components/VersionHistory'
import AgentGraph, { type StepRow } from '../components/AgentGraph'
import { requests, plans, execution } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import type { MaintenanceRequest, BlockPlan, Report, AffectedTrain, ExecutionInfo } from '../types'

export default function OfficerReview() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const requestId = parseInt(id || '0')

  const [requestData, setRequestData] = useState<(MaintenanceRequest & { plans: BlockPlan[] }) | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [showReject, setShowReject] = useState(false)
  const [approving, setApproving] = useState(false)
  const [approved, setApproved] = useState(false)
  const [blockId, setBlockId] = useState('')
  const [error, setError] = useState('')
  const [sanctioning, setSanctioning] = useState(false)
  const [sanction, setSanction] = useState<ExecutionInfo | null>(null)
  const [sanctionErr, setSanctionErr] = useState('')
  const [steps, setSteps] = useState<StepRow[]>([])
  const [replanning, setReplanning] = useState(false)
  const [rejectedReason, setRejectedReason] = useState('')
  const [replanTargetVersion, setReplanTargetVersion] = useState(0)
  const [liveView, setLiveView] = useState<'feed' | 'graph'>('feed')

  const { messages, connected, clearMessages } = useWebSocket(requestId)

  useEffect(() => { loadData() }, [requestId])

  const loadData = async () => {
    try {
      const req = await requests.get(requestId)
      setRequestData(req)
      if (req.status === 'REPLANNING') {
        setReplanning(true)
        setReplanTargetVersion(req.plans && req.plans.length > 0 ? req.plans[0].version : 0)
      }
      const r = await requests.getReport(requestId)
      setReport(r)
    } catch (err: any) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  // merge live replan websocket events
  useEffect(() => {
    if (messages.length === 0) return
    for (const msg of messages) {
      if (msg.event === 'agent_progress' && msg.data?.step) {
        setSteps(prev => upsertStep(prev, msg.data.step, msg.data.status, msg.data.data))
      } else if (msg.event === 'replanning_completed' || msg.event === 'report_ready') {
        setReplanning(false)
        setSteps([])
        setReplanTargetVersion(0)
        loadData()
      }
    }
  }, [messages])

  // polling fallback while replanning (catches events missed while disconnected)
  useEffect(() => {
    if (!replanning) return
    const interval = setInterval(async () => {
      try {
        const agents = await requests.getAgents(requestId, replanTargetVersion + 1)
        setSteps(prev => mergeSteps(prev, agents.map(a => ({ agent: a.agent_name, status: a.status, data: a.output_data }))))
        const req = await requests.get(requestId)
        const latest = req.plans && req.plans.length > 0 ? req.plans[0] : null
        if (latest && latest.version > replanTargetVersion && latest.status === 'PENDING_REVIEW') {
          setReplanning(false)
          setSteps([])
          setReplanTargetVersion(0)
          loadData()
        } else if (req.status === 'FAILED') {
          setReplanning(false)
          setSteps([])
          setReplanTargetVersion(0)
          loadData()
        }
      } catch {}
    }, 2500)
    return () => clearInterval(interval)
  }, [replanning, replanTargetVersion, requestId])

  const handleApprove = async () => {
    if (!report) return
    setApproving(true)
    try {
      const res = await plans.approve(report.plan.id)
      setBlockId(res.block_id)
      setApproved(true)
    } catch (err: any) {
      setError(err.message)
    } finally { setApproving(false) }
  }

  const handleReject = async (reason: string, avoidTime?: string, preferred?: string, constraint?: string) => {
    if (!report) return
    try {
      clearMessages()
      setSteps([])
      setRejectedReason(reason)
      setReplanTargetVersion(report.plan.version)
      await plans.reject(report.plan.id, {
        rejection_reason: reason,
        avoid_time: avoidTime,
        preferred_time: preferred,
        additional_constraint: constraint,
      })
      setReplanning(true)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleSanction = async () => {
    if (!report) return
    setSanctioning(true)
    setSanctionErr('')
    try {
      const res = await execution.sanction(report.plan.id)
      setSanction(res)
      setApproved(true)
    } catch (err: any) {
      setSanctionErr(err.message || 'Sanction failed')
    } finally {
      setSanctioning(false)
    }
  }

  if (loading) return <Layout title="Block Plan Review"><div className="text-center py-12 text-gray-500">Loading report...</div></Layout>
  if (error) return <Layout title="Block Plan Review"><div className="text-center py-12 text-red-500">{error}</div></Layout>
  if (!report) return <Layout title="Block Plan Review"><div className="text-center py-12 text-gray-500">No report available</div></Layout>

  const { plan, request: req } = report
  const affectedTrains: AffectedTrain[] = Array.isArray(plan.affected_trains) ? plan.affected_trains : []
  const blockStartMin = timeToMinutes(plan.start_time)
  const blockEndMin = timeToMinutes(plan.end_time)
  const timelineStart = 6 * 60
  const timelineEnd = 24 * 60

  if (approved) {
    return (
      <Layout title="Block Plan Approved">
        <div className="max-w-2xl mx-auto text-center py-12">
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <span className="text-4xl text-green-600">✓</span>
          </motion.div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Block {sanction ? 'Sanctioned' : 'Approved'}</h2>
          <p className="text-gray-600 mb-4">
            {sanction
              ? 'Block sanctioned. Notice and caution order generated — hand over to the field engineer.'
              : 'Maintenance block approved. Next: sanction the block to issue the working notice.'}
          </p>
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6 text-left">
            <p className="text-sm text-green-700">✓ Officer Approved</p>
            <p className="text-sm text-green-700">✓ Constraints Validated</p>
            <p className="text-sm text-green-700">{sanction ? '✓ Block Notice & Caution Order Issued' : '✓ Block Published'}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <p className="text-xs text-gray-500 mb-1">Block ID</p>
            <p className="text-xl font-bold text-gray-900 font-mono">{sanction?.block_id || blockId}</p>
          </div>

          {!sanction && !sanctioning && (
            <button onClick={handleSanction} className="bg-railway-accent text-white px-6 py-2 rounded-md hover:bg-railway-darkblue text-sm font-medium mb-2">
              📄 Sanction Block & Generate Notice
            </button>
          )}
          {sanctioning && <p className="text-sm text-gray-500 mb-2">Sanctioning…</p>}
          {sanctionErr && <p className="text-sm text-red-600 mb-2">{sanctionErr}</p>}

          <div className="flex justify-center gap-3">
            <button
              onClick={() => navigate(sanction ? '/live' : '/officer')}
              className="bg-railway-blue text-white px-6 py-2 rounded-md hover:bg-railway-darkblue text-sm font-medium"
            >
              {sanction ? '▶ Open Live Operations' : 'Back to Dashboard'}
            </button>
          </div>

          {sanction && sanction.block_notice && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-8 text-left bg-white rounded-xl border border-gray-200 p-4 max-h-72 overflow-y-auto">
              <p className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-2">Generated Block Notice</p>
              <pre className="text-[11px] font-mono whitespace-pre-wrap text-gray-700">{sanction.block_notice}</pre>
            </motion.div>
          )}
        </div>
      </Layout>
    )
  }

  return (
    <Layout title="Block Plan Review" subtitle={`Version ${plan.version}`}>
      <div className="max-w-5xl mx-auto">
        {replanning && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="glass-deep rounded-2xl border border-so-line2 p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-so-cyan" />
                <p className="h-overline mb-0">AGENTIC REPLANNING — LIVE</p>
              </div>
              <span className={`text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 ${connected ? 'text-so-green' : 'text-so-amber'}`}>
                <Radio className="w-3 h-3" /> {connected ? 'ws live' : 'ws polling'}
              </span>
            </div>

            {rejectedReason && (
              <div className="rounded-md border border-so-amber/40 bg-so-amber/10 px-3 py-2 text-xs text-so-amber mb-4">
                Version {replanTargetVersion} was rejected — feedback: “{rejectedReason}”.
                Regenerating plan version {replanTargetVersion + 1} with these constraints.
              </div>
            )}

            <div className="flex-1 h-1.5 bg-so-panel rounded-full overflow-hidden border border-so-line mb-4">
              <motion.div className="h-full bg-railway-accent rounded-full"
                animate={{ width: `${progressPct(steps)}%` }} transition={{ duration: 0.4 }} />
            </div>

            <div className="flex items-center gap-1 bg-so-panel/70 border border-so-line rounded-xl p-1 w-fit mb-4">
              <button onClick={() => setLiveView('feed')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${liveView === 'feed' ? 'bg-so-cyan/15 text-so-cyan border border-so-cyan/25' : 'text-so-dim'}`}>
                Status Feed
              </button>
              <button onClick={() => setLiveView('graph')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${liveView === 'graph' ? 'bg-so-cyan/15 text-so-cyan border border-so-cyan/25' : 'text-so-dim'}`}>
                Agent Graph
              </button>
            </div>

            {liveView === 'feed' ? <ReplanStatusFeed steps={steps} /> : <AgentGraph steps={steps} />}
          </motion.div>
        )}

        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">BLOCK PLAN REVIEW</h2>
            <p className="text-sm text-gray-500">Version {plan.version} | MR-{String(requestId).padStart(5, '0')}</p>
          </div>
          <div className="flex gap-2">
            <StatusBadge status={plan.status} />
            <PriorityBadge priority={req.priority} />
          </div>
        </div>

        {requestData && requestData.plans && requestData.plans.length > 1 && (
          <VersionHistory plans={requestData.plans} currentVersion={plan.version} />
        )}

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Maintenance Request</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Department</span><span className="font-medium">{req.department}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Type</span><span className="font-medium">{req.maintenance_type}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Work Type</span><span className="font-medium">{req.work_type || '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Section</span><span className="font-medium">{req.section}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Track / Line</span><span className="font-medium">{req.track_no || '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Date</span><span className="font-medium">{req.requested_date}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Duration</span><span className="font-medium">{req.duration_minutes} min</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Priority</span><span className="font-medium">{req.priority}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Crew Size</span><span className="font-medium">{req.crew_size ?? '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Est. Material Cost</span><span className="font-medium">{req.est_material_cost != null ? `₹${req.est_material_cost}` : '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Weather Sensitive</span><span className="font-medium">{req.weather_sensitive || '—'}</span></div>
              {req.equipment && <div className="flex justify-between gap-3"><span className="text-gray-500 shrink-0">Equipment</span><span className="font-medium text-right">{req.equipment}</span></div>}
              {req.special_instructions && <div className="flex justify-between gap-3"><span className="text-gray-500 shrink-0">Special</span><span className="font-medium text-right">{req.special_instructions}</span></div>}
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Recommended Block</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Date</span><span className="font-medium">{plan.proposed_date}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Start</span><span className="font-bold text-lg">{plan.start_time}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">End</span><span className="font-bold text-lg">{plan.end_time}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Duration</span><span className="font-medium">{plan.duration_minutes} min</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Section</span><span className="font-medium">{req.section}</span></div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-5 mb-6">
          <h3 className="font-semibold text-gray-900 mb-4 text-sm uppercase tracking-wide">Train Impact Timeline</h3>
          <div className="relative">
            <div className="flex items-center justify-between text-xs text-gray-400 mb-2 px-1">
              {[6, 8, 10, 12, 14, 16, 18, 20, 22, 24].map(h => (
                <span key={h}>{h.toString().padStart(2, '0')}:00</span>
              ))}
            </div>
            <div className="relative h-12 bg-gray-100 rounded mb-3">
              <div
                className="absolute h-full rounded flex items-center justify-center"
                style={{
                  left: `${((blockStartMin - timelineStart) / (timelineEnd - timelineStart)) * 100}%`,
                  width: `${((blockEndMin - blockStartMin) / (timelineEnd - timelineStart)) * 100}%`,
                  background: '#1D5FA7',
                  boxShadow: '0 4px 12px -6px rgba(11, 31, 58, 0.5)',
                }}
              >
                <span className="text-xs font-bold text-white">MAINTENANCE BLOCK</span>
              </div>
            </div>
            {affectedTrains.map((train, i) => (
              <div key={train.train_number} className="flex items-center gap-2 mb-1 text-xs">
                <span className="w-24 text-gray-600 font-medium truncate">{train.train_number}</span>
                <span className="flex-1 relative h-5 bg-gray-50 rounded">
                  <div
                    className="absolute h-full rounded"
                    style={{
                      left: `${((timeToMinutes(train.scheduled_arrival || train.arrival_time || '00:00') - timelineStart) / (timelineEnd - timelineStart)) * 100}%`,
                      width: '4px',
                      backgroundColor: (train.impact === 'HIGH' || train.priority === 'RAJDHANI' || train.priority === 'SHATABDI') ? '#B3261E' : '#A15C00',
                    }}
                  />
                </span>
                <span className="w-16 text-gray-500">{train.delay_minutes || train.estimated_delay_minutes || 0} min</span>
                <span className={`w-16 text-xs font-medium ${train.action === 'REROUTE' ? 'text-red-600' : train.action === 'HOLD' ? 'text-orange-600' : 'text-yellow-600'}`}>
                  {train.action || 'DELAY'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <OfficerReport
          rd={plan.report_data}
          plan={plan}
          approving={approving}
          canDecide={plan.status === 'PENDING_REVIEW'}
          onApprove={handleApprove}
          onReject={() => setShowReject(true)}
        />

        {(plan.status === 'APPROVED' || plan.status === 'PUBLISHED') && (
          <button
            onClick={handleSanction}
            disabled={sanctioning}
            className="w-full bg-railway-accent text-white py-3 rounded-md hover:bg-railway-darkblue transition-colors font-medium disabled:opacity-50"
          >
            📄 Sanction Block & Generate Notice {sanctioning ? '…' : ''}
          </button>
        )}
        {sanctionErr && <p className="text-sm text-red-600">{sanctionErr}</p>}
      </div>

      <RejectModal
        open={showReject}
        onClose={() => setShowReject(false)}
        onSubmit={handleReject}
      />
    </Layout>
  )
}

function timeToMinutes(time: string): number {
  if (!time) return 0
  const parts = time.split(':')
  return parseInt(parts[0]) * 60 + parseInt(parts[1] || '0')
}

const REPLAN_STEP_LABEL: Record<string, string> = {
  request_received: 'Request received',
  data_validation: 'Validating request data',
  maintenance_agent: 'Analyzing maintenance requirements',
  traffic_agent: 'Analyzing live train traffic',
  priority_agent: 'Prioritizing the block window',
  historical_agent: 'Matching historical block patterns',
  rag_retrieval: 'Retrieving policy references',
  web_research: 'Checking external advisories',
  evidence_validation: 'Validating engineering evidence',
  candidate_generation: 'Generating candidate block windows',
  cp_sat_optimization: 'Optimizing block window (CP-SAT)',
  simulation: 'Simulating delay impact on trains',
  routing_analysis: 'Proposing diversions / reroutes',
  route_optimization: 'Finalizing operational routing',
  hard_conflict_gate: 'Running hard-conflict gate',
  constraint_validation: 'Checking constraints & compliance',
  risk_compliance: 'Assessing risk & compliance',
  decision_fusion: 'Fusing agent decisions',
  report_generation: 'Writing the AI report',
  workflow_failed: 'Workflow failed',
}

function ReplanStatusFeed({ steps }: { steps: StepRow[] }) {
  if (steps.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-so-dim">
        <span className="w-2 h-2 rounded-full bg-so-cyan animate-pulse" />
        Orchestrator warming up — incorporating officer feedback into replanning…
      </div>
    )
  }
  const rows = steps.slice(-12).reverse()
  return (
    <div className="flex flex-col gap-2">
      {rows.map((s, i) => {
        const done = s.status === 'completed'
        const running = s.status === 'in_progress' || s.status === 'running' || s.status === 'queued'
        const failed = s.status === 'failed'
        const label = REPLAN_STEP_LABEL[s.agent] || s.agent
        return (
          <div key={`${s.agent}-${i}`} className="flex items-start gap-2.5 text-xs leading-relaxed">
            <span className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
              done ? 'bg-so-green' : failed ? 'bg-so-red' : running ? 'bg-so-cyan animate-pulse' : 'bg-so-dim'
            }`} />
            <span className={done ? 'text-so-text' : failed ? 'text-so-red' : 'text-so-text'}>
              {label}
            </span>
            <span className={`ml-auto shrink-0 ${done ? 'text-so-green' : failed ? 'text-so-red' : 'text-so-dim'}`}>
              {done ? '✓ done' : failed ? '✕ failed' : running ? 'in progress…' : s.status}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function upsertStep(prev: StepRow[], name: string, status: string, data?: any): StepRow[] {
  const idx = prev.findIndex(s => s.agent === name)
  const row: StepRow = { agent: name, status, data }
  if (idx === -1) return [...prev, row]
  const next = [...prev]
  next[idx] = row
  return next
}

function mergeSteps(prev: StepRow[], polled: StepRow[]): StepRow[] {
  let out = [...prev]
  for (const row of polled) out = upsertStep(out, row.agent, row.status, row.data)
  return out
}

function progressPct(steps: StepRow[]): number {
  const doneCount = steps.filter(s => s.status === 'completed').length
  const total = 21
  return Math.min(100, Math.round((doneCount / total) * 100))
}
