import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldCheck, AlertTriangle, RefreshCcw, CheckCircle2, Ban, ClipboardCheck } from 'lucide-react'
import Layout from '../components/Layout'
import StatusBadge, { PriorityBadge, RiskBadge } from '../components/StatusBadge'
import { dashboard } from '../services/api'
import type { OfficerDashboard as DashData } from '../types'

export default function OfficerDashboard() {
  const [data, setData] = useState<DashData | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => { loadData() }, [])

  useEffect(() => {
    const iv = setInterval(() => { loadData() }, 10000)
    return () => clearInterval(iv)
  }, [])

  const loadData = async () => {
    try {
      const d = await dashboard.officer()
      setData(d)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  if (loading) return <Layout title="Officer Portal"><div className="text-center py-12 text-so-dim">Loading...</div></Layout>
  if (!data) return <Layout title="Officer Portal"><div className="text-center py-12 text-so-red">Failed to load</div></Layout>

  const { stats } = data
  const cards = [
    { label: 'Pending Approvals', value: stats.pending_approvals, icon: ClipboardCheck, valueCls: 'text-so-cyan', chipCls: 'border-so-cyan/30 bg-so-cyan/10', tile: 'shadow-glow' },
    { label: 'High Risk', value: stats.high_risk, icon: AlertTriangle, valueCls: 'text-so-red', chipCls: 'border-so-red/30 bg-so-red/10', tile: '' },
    { label: 'Replanning', value: stats.replanning, icon: RefreshCcw, valueCls: 'text-so-amber', chipCls: 'border-so-amber/30 bg-so-amber/10', tile: '' },
    { label: 'Approved Today', value: stats.approved_today, icon: CheckCircle2, valueCls: 'text-so-green', chipCls: 'border-so-green/30 bg-so-green/10', tile: '' },
    { label: 'Published Blocks', value: stats.published_blocks, icon: ShieldCheck, valueCls: 'text-so-violet', chipCls: 'border-so-violet/30 bg-so-violet/10', tile: '' },
  ]

  return (
    <Layout title="Officer Control Portal">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-so-text">Officer Dashboard</h2>
        <p className="text-sm text-so-dim mt-0.5">Review and approve maintenance block plans</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {cards.map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`glass-deep rounded-xl border border-so-line2 p-4 ${card.tile}`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className={`chip border ${card.chipCls}`}>
                <card.icon className="w-3 h-3" />
              </span>
            </div>
            <p className={`text-3xl font-extrabold font-mono ${card.valueCls}`}>{card.value}</p>
            <p className="text-xs text-so-dim mt-1 font-medium">{card.label}</p>
          </motion.div>
        ))}
      </div>

      <div className="mb-4">
        <h3 className="font-bold text-so-text mb-3 text-base">Pending Reviews</h3>
      </div>

      {data.pending_requests.length === 0 ? (
        <div className="glass-deep rounded-xl border border-so-line p-8 text-center">
          <Ban className="w-8 h-8 text-so-green mx-auto mb-3" />
          <p className="text-sm text-so-dim font-medium">No pending requests for review</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {data.pending_requests.map((req) => (
            <motion.div
              key={req.id}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-deep rounded-xl border border-so-line p-5 hover:border-so-line2 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <span className="font-mono text-sm text-so-dim">MR-{String(req.id).padStart(5, '0')}</span>
                    <StatusBadge status={req.status} />
                    <PriorityBadge priority={req.priority} />
                  </div>
                  <h4 className="font-semibold text-so-text">{req.maintenance_type} - {req.section}</h4>
                  <p className="text-sm text-so-dim mt-1">
                    {req.department} | {req.duration_minutes} min | {req.requested_date} | Engineer: {req.engineer_name || 'Unknown'}
                  </p>

                  {req.latest_plan && (
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mt-3 text-sm">
                      <div>
                        <span className="text-so-dim">Block:</span>{' '}
                        <span className="font-semibold text-so-text font-mono">{req.latest_plan.start_time} - {req.latest_plan.end_time}</span>
                        <span className="text-so-dim ml-1">(V{req.latest_plan.version})</span>
                      </div>
                      <div>
                        <span className="text-so-dim">Trains:</span>{' '}
                        <span className="font-semibold text-so-text">{Array.isArray(req.latest_plan.affected_trains) ? req.latest_plan.affected_trains.length : 0} affected</span>
                      </div>
                      <div>
                        <span className="text-so-dim">Delay:</span>{' '}
                        <span className="font-semibold text-so-text font-mono">{req.latest_plan.estimated_delay_minutes} min</span>
                      </div>
                      <RiskBadge level={req.latest_plan.risk_score < 30 ? 'LOW' : req.latest_plan.risk_score < 60 ? 'MEDIUM' : 'HIGH'} />
                      <div>
                        <span className="text-so-dim">Confidence:</span>{' '}
                        <span className="font-semibold text-so-text">{req.latest_plan.confidence}%</span>
                      </div>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => navigate(`/officer/review/${req.id}`)}
                  className="btn-rail text-[13px] px-5 py-2 shrink-0 ml-4"
                >
                  Review Plan
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </Layout>
  )
}