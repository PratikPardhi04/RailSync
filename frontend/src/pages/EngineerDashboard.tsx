import { Fragment, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, GitBranch, Check } from 'lucide-react'
import Layout from '../components/Layout'
import StatusBadge, { PriorityBadge } from '../components/StatusBadge'
import OfficerReport from '../components/OfficerReport'
import { dashboard, requests as requestsApi } from '../services/api'
import type { EngineerDashboard as DashData, MaintenanceRequest, BlockPlan, Report } from '../types'

const TRACK: { stage: string; matches: (req: MaintenanceRequest, plan?: BlockPlan) => boolean }[] = [
  { stage: 'Submitted', matches: (r) => ['PENDING', 'SUBMITTED', 'DRAFT', 'VALIDATING'].includes(r.status) },
  { stage: 'AI Analysis', matches: (r) => ['AI_ANALYSIS', 'OPTIMIZING', 'SIMULATING'].includes(r.status) },
  { stage: 'Report Ready', matches: (r, p) => ['REPORT_READY', 'AWAITING_OFFICER'].includes(r.status) && !['APPROVED', 'PUBLISHED', 'REJECTED'].includes(p?.status || '') },
  { stage: 'Officer Review', matches: (r, p) => (p?.status || '') === 'PENDING_REVIEW' },
  { stage: 'Approved', matches: (r, p) => ['APPROVED', 'PUBLISHED'].includes(p?.status || '') },
  { stage: 'Rejected', matches: (r, p) => (p?.status || '') === 'REJECTED' },
]

function currentStage(req: MaintenanceRequest, plan?: BlockPlan): string {
  for (const t of TRACK) if (t.matches(req, plan)) return t.stage
  return 'Submitted'
}

function StatusTrack({ req, plan }: { req: MaintenanceRequest; plan?: BlockPlan }) {
  const current = currentStage(req, plan)
  const steps = TRACK.map(t => t.stage)
  const stopIdx = current === 'Rejected' ? steps.indexOf('Rejected') : (steps.includes(current) ? steps.indexOf(current) + 1 : steps.length)
  const rejected = current === 'Rejected'

  return (
    <div className="flex items-center flex-wrap gap-1.5">
      {steps.map((s, i) => {
        const passed = i < stopIdx && !rejected
        const active = s === current
        return (
          <div key={s} className="flex items-center">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${
                active
                  ? 'bg-railway-accent text-white border-railway-accent'
                  : rejected && i === stopIdx
                    ? 'bg-red-50 text-red-700 border-red-200'
                    : i < stopIdx
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-gray-50 text-gray-400 border-gray-200'
              }`}
            >
              {i < stopIdx && !active && <Check className="w-3 h-3" />}
              {s}
            </span>
            {i < steps.length - 1 && <ChevronRight />}
          </div>
        )
      })}
    </div>
  )
}

function ChevronRight() {
  return (
    <svg className="w-3.5 h-3.5 text-gray-300 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m9 18 6-6-6-6" />
    </svg>
  )
}

export default function EngineerDashboard() {
  const [data, setData] = useState<DashData | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [reportMap, setReportMap] = useState<Record<number, Report>>({})
  const [reportErr, setReportErr] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    const iv = setInterval(() => { loadData() }, 10000)
    return () => clearInterval(iv)
  }, [])

  // refresh the open report when a newer plan version lands (e.g. after officer rejection + replan)
  useEffect(() => {
    if (expandedId == null) return
    const iv = setInterval(async () => {
      try {
        const rep = await requestsApi.getReport(expandedId)
        setReportMap(prev => (prev[expandedId]?.plan?.version === rep.plan?.version ? prev : { ...prev, [expandedId]: rep }))
        loadData()
      } catch {}
    }, 8000)
    return () => clearInterval(iv)
  }, [expandedId])

  const loadData = async () => {
    try {
      const d = await dashboard.engineer()
      setData(d)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const toggleRow = async (req: MaintenanceRequest) => {
    const next = expandedId === req.id ? null : req.id
    setExpandedId(next)
    setReportErr('')
    if (next != null && !reportMap[next]) {
      try {
        const rep = await requestsApi.getReport(next)
        setReportMap(prev => ({ ...prev, [next]: rep }))
      } catch (err: any) {
        setReportErr(err.message || 'Failed to load report')
      }
    }
  }

  if (loading) return <Layout title="Engineer Portal"><div className="text-center py-12 text-gray-500">Loading dashboard...</div></Layout>
  if (!data) return <Layout title="Engineer Portal"><div className="text-center py-12 text-red-500">Failed to load dashboard</div></Layout>

  const stats = data.stats
  const cards = [
    { label: 'Total Requests', value: stats.total_requests, tone: '' },
    { label: 'Pending', value: stats.pending, tone: 'stat-card--blue' },
    { label: 'AI Processing', value: stats.ai_processing, tone: 'stat-card--purple' },
    { label: 'Awaiting Approval', value: stats.awaiting_approval, tone: 'stat-card--amber' },
    { label: 'Approved', value: stats.approved, tone: 'stat-card--green' },
    { label: 'Rejected', value: stats.rejected, tone: 'stat-card--red' },
  ]

  return (
    <Layout title="Engineer Portal">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Dashboard</h2>
          <p className="text-sm text-gray-500">Overview of maintenance block requests</p>
        </div>
        <button
          onClick={() => navigate('/engineer/new')}
          className="bg-railway-blue text-white px-4 py-2 rounded-md hover:bg-railway-darkblue transition-colors font-medium text-sm"
        >
          + Raise Block Request
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {cards.map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`stat-card rounded-lg border p-4 ${card.tone}`}
          >
            <p className="stat-value text-2xl font-bold">{card.value}</p>
            <p className="stat-label text-xs mt-1">{card.label}</p>
          </motion.div>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Requests</h3>
          <span className="text-xs text-gray-400">Expand a row to view its generated report</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Section</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Department</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Priority</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Date</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Request Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Plan</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_requests.map((req) => {
                const isOpen = expandedId === req.id
                const plan = req.latest_plan
                const rep = reportMap[req.id]
                return (
                  <Fragment key={req.id}>
                    <tr className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer" onClick={() => toggleRow(req)}>
                      <td className="px-4 py-3 font-mono text-xs">MR-{String(req.id).padStart(5, '0')}</td>
                      <td className="px-4 py-3">{req.section}</td>
                      <td className="px-4 py-3">{req.department}</td>
                      <td className="px-4 py-3 text-gray-500">{req.maintenance_type}</td>
                      <td className="px-4 py-3"><PriorityBadge priority={req.priority} /></td>
                      <td className="px-4 py-3 text-gray-500">{req.requested_date}</td>
                      <td className="px-4 py-3"><StatusBadge status={req.status} /></td>
                      <td className="px-4 py-3 text-center">{plan ? <>V{plan.version}</> : '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="text-railway-accent hover:text-blue-800 text-xs font-medium inline-flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5" /> {isOpen ? 'Hide Report' : 'Report'}
                          </span>
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/engineer/request/${req.id}`) }}
                            className="text-railway-accent hover:text-blue-800 text-xs font-medium"
                          >
                            View
                          </button>
                        </div>
                      </td>
                    </tr>
                    <AnimatePresence>
                      {isOpen && (
                        <motion.tr key={`row-${req.id}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                          <td colSpan={9} className="px-6 py-6 bg-gray-50/60">
                            <div className="flex items-center gap-2 mb-4 flex-wrap">
                              <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-400 shrink-0">
                                <GitBranch className="w-3.5 h-3.5" /> Status Track
                              </span>
                              <StatusTrack req={req} plan={plan} />
                            </div>
                            {reportErr && <p className="text-xs text-red-600 mb-3">{reportErr}</p>}
                            {!rep ? (
                              <p className="text-sm text-gray-500">Loading generated report...</p>
                            ) : rep.plan?.report_data?.officer_report ? (
                              <OfficerReport rd={rep.plan.report_data} plan={rep.plan} readOnly />
                            ) : (
                              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800">
                                No enriched report yet for this request — run or wait for analysis.
                              </div>
                            )}
                          </td>
                        </motion.tr>
                      )}
                    </AnimatePresence>
                  </Fragment>
                )
              })}
              {data.recent_requests.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">No requests found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}