import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Cpu, Play, RefreshCcw, Radio, FileText, AlertTriangle, ArrowRight, ClipboardCheck } from 'lucide-react'
import Layout from '../components/Layout'
import StatusBadge from '../components/StatusBadge'
import AgentGraph, { type StepRow } from '../components/AgentGraph'
import OfficerReport from '../components/OfficerReport'
import { requests } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import type { MaintenanceRequest, Report } from '../types'

const LIVE_STATUSES = ['PENDING', 'SUBMITTED', 'VALIDATING', 'AI_ANALYSIS', 'OPTIMIZING', 'SIMULATING', 'AI_ANALYZING', 'PROCESSING', 'REPLANNING']
const END_STATUSES = ['REPORT_READY', 'AWAITING_OFFICER', 'APPROVED', 'PUBLISHED', 'FAILED', 'REJECTED', 'PENDING_REVIEW']

const STEP_LABEL: Record<string, string> = {
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

export default function AIProcessing() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const requestId = parseInt(id || '0')

  const [requestData, setRequestData] = useState<MaintenanceRequest | null>(null)
  const [steps, setSteps] = useState<StepRow[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState<'graph' | 'report'>('graph')
  const [selected, setSelected] = useState<string | null>(null)
  const autoStartedRef = useRef(false)

  const { messages, connected, clearMessages } = useWebSocket(requestId)

  const isRunning = useMemo(
    () => !done && !error && (analyzing || (requestData ? LIVE_STATUSES.includes(requestData.status) : true)),
    [done, error, analyzing, requestData]
  )

  const failed = error !== '' || requestData?.status === 'FAILED'

  // merge live websocket events into step map
  useEffect(() => {
    if (messages.length === 0) return
    for (const msg of messages) {
      if (msg.event === 'agent_progress' && msg.data?.step) {
        setSteps(prev => upsertStep(prev, msg.data.step, msg.data.status, msg.data.data))
      } else if (msg.event === 'report_ready') {
        setView('report')
        setDone(true)
        loadReport()
      }
    }
  }, [messages])

  const loadRequest = useCallback(async () => {
    try {
      const data = await requests.get(requestId)
      setRequestData(data)
      if (END_STATUSES.includes(data.status)) setDone(true)
    } catch (err: any) {
      setError(err.message)
    }
  }, [requestId])

  const loadReport = useCallback(async (force = false) => {
    try {
      const r = await requests.getReport(requestId)
      setReport(r)
      if (force) setDone(true)
    } catch {}
  }, [requestId])

  // initial load
  useEffect(() => {
    loadRequest()
  }, [loadRequest])

  // polling fallback (also catches events missed while disconnected)
  useEffect(() => {
    if (done || error) return
    const interval = setInterval(async () => {
      try {
        const data = await requests.get(requestId)
        setRequestData(data)
        const agents = await requests.getAgents(requestId)
        const merged: StepRow[] = []
        for (const a of agents) merged.push({ agent: a.agent_name, status: a.status, data: a.output_data })
        setSteps(prev => mergeSteps(prev, merged))
        if (END_STATUSES.includes(data.status)) {
          setDone(true)
          setView('report')
          loadReport()
        } else if (data.status === 'FAILED') {
          setError('Analysis failed. No feasible, compliant block could be produced within retry bounds.')
        }
      } catch {}
    }, 2500)
    return () => clearInterval(interval)
  }, [requestId, done, error, loadReport])

  // auto-start the pipeline as soon as the page opens if analysis has not begun yet
  useEffect(() => {
    if (autoStartedRef.current) return
    if (!requestData || done || error) return
    if (['PENDING', 'SUBMITTED', 'VALIDATING'].includes(requestData.status)) {
      autoStartedRef.current = true
      startAnalysis()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestData, done, error])

  const startAnalysis = async () => {
    setAnalyzing(true)
    setError('')
    setDone(false)
    setReport(null)
    setView('graph')
    clearMessages()
    setSteps([])
    try {
      await requests.analyze(requestId)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const showReport = () => { loadReport(true); setView('report') }

  if (error) {
    return (
      <Layout title="Agent Pipeline" subtitle={requestData ? `MR-${String(requestId).padStart(5, '0')}` : 'System'}>
        <div className="max-w-3xl mx-auto">
          <div className="glass-deep rounded-2xl p-8 text-center border border-so-red/40">
            <AlertTriangle className="w-10 h-10 text-so-red mx-auto mb-3" />
            <p className="text-so-text font-bold mb-1">Analysis interrupted</p>
            <p className="text-xs text-so-dim mb-5">{error}</p>
            <button onClick={() => { setError(''); startAnalysis() }} className="btn-rail inline-flex items-center gap-2">
              <RefreshCcw className="w-4 h-4" /> Retry Analysis
            </button>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout title="Agent Pipeline" subtitle={requestData ? `MR-${String(requestId).padStart(5, '0')}` : `Request ${requestId}`}>
      <div className="max-w-6xl mx-auto space-y-5">
        {/* request header */}
        {requestData && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="glass rounded-2xl border border-so-line2 overflow-hidden">
            <div className="h-0.5 bg-so-cyan" />
            <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-so-cyan/15 border border-so-cyan/30 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-so-cyan" />
                </div>
                <div>
                  <h3 className="font-bold text-so-text">{requestData.maintenance_type}</h3>
                  <p className="text-xs text-so-dim">{requestData.section} • {requestData.department}</p>
                  <p className="text-[11px] text-so-dim mt-0.5">
                    {requestData.work_type ? `${requestData.work_type} • ` : ''}{requestData.duration_minutes} min • {requestData.priority}
                    {requestData.track_no ? ` • Track ${requestData.track_no}` : ''}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 ${connected ? 'text-so-green' : 'text-so-amber'}`}>
                  <Radio className="w-3 h-3" /> {connected ? 'ws live' : 'ws polling'}
                </span>
                <StatusBadge status={requestData.status} />
              </div>
            </div>

            {isRunning && (
              <div className="px-5 py-3 border-t border-so-line flex items-center gap-4">
                <div className="flex-1 h-1.5 bg-so-panel rounded-full overflow-hidden border border-so-line">
                  <motion.div className="h-full bg-railway-accent rounded-full"
                    animate={{ width: `${progressPct(steps)}%` }} transition={{ duration: 0.4 }} />
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {!done && (
                    <button onClick={startAnalysis} className="btn-rail inline-flex items-center gap-1.5 h-8">
                      <RefreshCcw className="w-3.5 h-3.5" /> Re-run
                    </button>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* launch CTA */}
        {!done && !isRunning && requestData && !END_STATUSES.includes(requestData.status) && report === null && (
          <div className="glass-deep rounded-2xl p-10 text-center">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-so-cyan/10 border border-so-line2
              flex items-center justify-center mb-4">
              <Cpu className="w-7 h-7 text-so-cyan" />
            </div>
            <p className="text-so-text font-bold text-lg">Ready to run the agent pipeline</p>
            <p className="text-xs text-so-dim mt-1 mb-6">LangGraph orchestration · CP-SAT · simulation · hard-conflict gate loops</p>
            <button onClick={startAnalysis} className="btn-rail inline-flex items-center gap-2 px-8 py-3 text-sm">
              <Play className="w-4 h-4" /> Start AI Analysis
            </button>
          </div>
        )}

        {/* live status feed (linear text) */}
        {isRunning && !done && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
            <div className="glass-deep rounded-2xl p-5">
              <p className="h-overline mb-4">LANGGRAPH ORCHESTRATION — LIVE STATUS</p>
              <StatusFeed steps={steps} />
            </div>
          </motion.div>
        )}

        {/* completion → report */}
        <AnimatePresence>
          {done && report && (
            <motion.div key="report" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
              <motion.div key="status" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="glass rounded-2xl border border-so-line2 px-5 py-4 flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-so-dim shrink-0">
                  <ClipboardCheck className="w-3.5 h-3.5" /> Application Status
                </span>
                <StatusBadge status={requestData?.status || 'SUBMITTED'} />
                <ArrowRight className="w-3.5 h-3.5 text-so-dim shrink-0" />
                <StatusBadge status={report.plan?.status || 'GENERATED'} />
                <span className="text-xs text-so-dim shrink-0">
                  {report.plan?.status === 'PENDING_REVIEW'
                    ? 'Plan is with the officer for approval — you will be notified once decided.'
                    : report.plan?.status === 'APPROVED' || report.plan?.status === 'PUBLISHED'
                      ? 'Plan approved and published by the officer.'
                      : report.plan?.status === 'REJECTED'
                        ? 'Plan rejected; the officer has requested a revised plan.'
                        : 'Plan analysis complete.'}
                </span>
              </motion.div>

              <div className="flex items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-2">
                  <span className="chip border bg-so-green/12 text-so-green border-so-green/35">
                    <FileText className="w-3 h-3" /> Plan report ready
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 bg-so-panel/70 border border-so-line rounded-xl p-1">
                    <button onClick={() => setView('report')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${view === 'report' ? 'bg-so-cyan/15 text-so-cyan border border-so-cyan/25' : 'text-so-dim'}`}>
                      Report
                    </button>
                    <button onClick={() => setView('graph')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${view === 'graph' ? 'bg-so-cyan/15 text-so-cyan border border-so-cyan/25' : 'text-so-dim'}`}>
                      Agent Graph
                    </button>
                  </div>
                  <button onClick={startAnalysis} className="btn-ghost inline-flex items-center gap-1.5 h-8">
                    <RefreshCcw className="w-3.5 h-3.5" /> Re-run
                  </button>
                </div>
              </div>
              {view === 'report' ? (
                <div className="bg-transparent">
                  <OfficerReport rd={report.plan?.report_data} plan={report.plan} readOnly />
                </div>
              ) : (
                <div className="glass-deep rounded-2xl p-5">
                  <p className="h-overline mb-4">LANGGRAPH TOPOLOGY — RUN COMPLETE</p>
                  <AgentGraph steps={steps} failed={failed} selected={selected} onSelect={setSelected} />
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* navigate back */}
        {done && report && (
          <div className="text-center">
            <button onClick={() => navigate('/engineer')} className="btn-ghost text-xs">
              ← Back to Engineer Dashboard
            </button>
          </div>
        )}
      </div>
    </Layout>
  )
}

function StatusFeed({ steps }: { steps: StepRow[] }) {
  if (steps.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-so-dim">
        <span className="w-2 h-2 rounded-full bg-so-cyan animate-pulse" />
        Orchestrator warming up — connecting to agents…
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
        const label = STEP_LABEL[s.agent] || s.agent
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