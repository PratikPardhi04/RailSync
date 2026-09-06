import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Layout from '../components/Layout'
import { live, execution } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import type { LiveState, WeatherInfo, LiveBlock, LiveTrain, LiveConflict } from '../types'

const TRAIN_TYPE_COLORS: Record<string, string> = {
  Rajdhani: 'bg-red-100 text-red-700 border-red-200',
  Shatabdi: 'bg-orange-100 text-orange-700 border-orange-200',
  Express: 'bg-blue-100 text-blue-700 border-blue-200',
  Superfast: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  Passenger: 'bg-slate-100 text-slate-600 border-slate-200',
  Freight: 'bg-stone-100 text-stone-600 border-stone-200',
}

const EXEC_STEPS = ['SANCTIONED', 'IN_POSITION', 'BLOCK_ACTIVE', 'RELEASED', 'COMPLETED']

export default function LiveOps() {
  const { user } = useAuth()
  const [state, setState] = useState<LiveState | null>(null)
  const [weather, setWeather] = useState<WeatherInfo | null>(null)
  const [speed, setSpeed] = useState(30)
  const [running, setRunning] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<string>('')
  const [noticePlan, setNoticePlan] = useState<number | null>(null)
  const [execMap, setExecMap] = useState<Record<number, any>>({})

  const refresh = useCallback(async () => {
    try {
      const ns = await live.state()
      setState(ns)
      setSpeed(ns.speed)
      setRunning(ns.running)
      const w = await live.weather()
      setWeather(w)
    } catch {}
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [refresh])

  const changeSpeed = async (v: number) => {
    setSpeed(v)
    await live.speed(v)
  }

  const toggleRunning = async () => {
    const nr = !running
    setRunning(nr)
    await live.running(nr)
  }

  const jump = async (m: number) => {
    await live.jump(m)
    refresh()
  }

  const doAction = async (action: string, planId: number) => {
    setBusy(`${action}:${planId}`)
    setError('')
    try {
      const fn = (execution as any)[action]
      const res = await fn(planId)
      setExecMap(prev => ({ ...prev, [planId]: res }))
      refresh()
    } catch (e: any) {
      setError(e.message || `Action ${action} failed`)
    } finally {
      setBusy('')
    }
  }

  const loadExec = async (planId: number) => {
    try {
      const ex = await execution.get(planId)
      setExecMap(prev => ({ ...prev, [planId]: ex }))
    } catch {}
  }

  useEffect(() => {
    if (!state) return
    state.blocks.forEach(b => {
      if (b.status !== 'SANCTIONED' && !execMap[b.plan_id]) loadExec(b.plan_id)
    })
  }, [state, execMap])

  const isOfficer = user?.role === 'officer'

  return (
    <Layout title="Live Operations" subtitle={`Simulated live train board • ${state?.sim_date || ''}`}>
      <div className="space-y-5">
        {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700 text-center">{error}</div>}

        {/* Sim control bar */}
        <div className="bg-railway-darkblue rounded-2xl p-5 shadow-lg">
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <p className="text-xs text-blue-200 uppercase tracking-wide">Simulated Time</p>
              <p className="text-3xl font-mono font-bold text-white leading-tight">
                {state?.sim_time || '--:--'}
                <span className="text-base text-blue-200 ml-2">{state?.running ? '▶' : '⏸'}</span>
              </p>
              <p className="text-xs text-blue-300">{state ? `${state.trains.filter(t => t.status !== 'NOT_DUE').length}/${state.trains.length} trains on move` : ''}</p>
            </div>

            <div className="flex-1 min-w-[200px]">
              <div className="flex items-center justify-between text-xs text-blue-200 mb-1.5">
                <span>Playback speed</span>
                <span>{speed}×</span>
              </div>
              <input
                type="range" min={1} max={300} step={1} value={speed}
                onChange={e => changeSpeed(parseInt(e.target.value))}
                className="w-full accent-[#18794E]"
              />
              <div className="flex gap-2 mt-3">
                <button onClick={toggleRunning} className="px-3 py-1.5 rounded-lg bg-white/10 text-white text-xs hover:bg-white/20 transition-colors font-medium">
                  {running ? '⏸ Pause' : '▶ Resume'}
                </button>
                <button onClick={() => jump(30)} className="px-3 py-1.5 rounded-lg bg-white/10 text-white text-xs hover:bg-white/20 transition-colors font-medium">+30 min</button>
                <button onClick={() => jump(120)} className="px-3 py-1.5 rounded-lg bg-white/10 text-white text-xs hover:bg-white/20 transition-colors font-medium">+2 hr</button>
              </div>
            </div>

            {weather && (
              <div className="bg-white/10 rounded-xl px-4 py-2.5 text-white">
                <p className="text-xs text-blue-200 uppercase tracking-wide">Weather · {weather.source}</p>
                <p className="text-sm font-semibold">{weather.condition}</p>
                <p className="text-xs text-blue-200">
                  {weather.temperature_c}°C · precip {weather.precipitation_probability}% · wind {weather.wind_kmh} km/h
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Train board */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Train Movement Board</h3>
              <span className="text-xs text-gray-400">{state?.trains.filter(t => t.status !== 'NOT_DUE').length || 0} active on {state?.trains[0]?.section || 'section'}</span>
            </div>
            <div className="space-y-1.5">
              {state?.trains.map(t => (
                <TrainRow key={t.train_number} train={t} />
              ))}
              {!state?.trains.length && <p className="text-sm text-gray-400 py-6 text-center">Loading …</p>}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-5">
            {/* Blocks */}
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Sanctioned Blocks</h3>
              {state?.blocks.length === 0 && <p className="text-sm text-gray-400">No sanctioned blocks yet. Approve & sanction a plan to see it here.</p>}
              <div className="space-y-3">
                {state?.blocks.map(b => (
                  <BlockCard
                    key={b.block_id}
                    block={b}
                    exec={execMap[b.plan_id]}
                    isOfficer={isOfficer}
                    busy={busy}
                    onAction={doAction}
                    onViewNotice={p => setNoticePlan(p)}
                  />
                ))}
              </div>
            </div>

            {/* Conflicts */}
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
              <h3 className="font-semibold text-gray-900 mb-3">⚠ Live Conflicts</h3>
              {state?.conflicts.length === 0 ? (
                <p className="text-sm text-emerald-600">No conflicts detected.</p>
              ) : (
                <div className="space-y-3">
                  {state?.conflicts.map(c => (
                    <ConflictCard key={`${c.train_number}-${c.block_id}`} conflict={c} isOfficer={isOfficer} onReplan={() => doAction('dynamicReplan', c.plan_id)} busy={busy} />
                  ))}
                </div>
              )}
            </div>

            {/* Events */}
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Live Event Feed</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {state?.events.map((e, i) => (
                  <div key={i} className="text-xs flex gap-2">
                    <span className="font-mono text-gray-400 shrink-0">{e.time}</span>
                    <span className={`shrink-0 px-1.5 rounded ${kindColor(e.kind)}`}>{e.kind}</span>
                    <span className="text-gray-600">{e.text}</span>
                  </div>
                ))}
                {state?.events.length === 0 && <p className="text-sm text-gray-400">No events yet.</p>}
              </div>
            </div>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {noticePlan != null && execMap[noticePlan] && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={() => setNoticePlan(null)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }}
              className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900">Block Artifacts — {execMap[noticePlan].block_id}</h3>
                <button onClick={() => setNoticePlan(null)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
              </div>
              <div className="space-y-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Block Notice</p>
                  <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-[11px] font-mono leading-relaxed whitespace-pre-wrap">{execMap[noticePlan].block_notice}</pre>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Caution Order</p>
                  <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-[11px] font-mono leading-relaxed whitespace-pre-wrap">{execMap[noticePlan].caution_order}</pre>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Layout>
  )
}

function TrainRow({ train }: { train: LiveTrain }) {
  const pct = Math.round(train.position * 100)
  const isMoving = train.status !== 'NOT_DUE' && train.status !== 'DEPARTED'
  return (
    <div className={`flex items-center gap-3 px-2 py-1.5 rounded-lg ${train.premium ? 'bg-red-50/60' : 'bg-transparent'} ${isMoving ? '' : 'opacity-60'}`}>
      <div className="w-52 shrink-0">
        <p className="text-sm font-medium text-gray-800 truncate" title={train.train_name}>
          {train.train_name}
          <span className="text-gray-400 ml-1 font-mono text-xs">{train.train_number}</span>
        </p>
        <p className="text-[10px] text-gray-400 truncate">{train.origin} → {train.destination}</p>
      </div>
      <span className={`shrink-0 px-2 py-0.5 rounded border text-[10px] font-semibold ${TRAIN_TYPE_COLORS[train.train_type] || 'bg-gray-100 text-gray-600'}`}>
        {train.train_type.toUpperCase()}
      </span>
      <div className="flex-1">
        <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
          <span>arr {train.scheduled_arrival}</span>
          <span>proj {train.projected_arrival}{train.delay_minutes > 0 ? ` (+${train.delay_minutes}m)` : ''}</span>
        </div>
        <div className="relative h-2.5 bg-gray-100 rounded-full overflow-hidden">
          <motion.div
            className={`absolute inset-y-0 left-0 rounded-full ${train.premium ? 'bg-red-500' : 'bg-blue-500'}`}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1 }}
          />
          {train.status === 'IN_SECTION' && (
            <div className="absolute inset-y-0 left-1/2 w-0.5 bg-gray-300" />
          )}
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
          <span>{train.origin}</span>
          <span>{train.section.split(' - ')[0]}</span>
          <span>{train.section.split(' - ')[1] || train.destination}</span>
          <span>{train.destination}</span>
        </div>
      </div>
      <div className="w-24 shrink-0 text-right">
        <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full ${statusColor(train.status)}`}>{train.status.replace('_', ' ')}</span>
        {train.held_by && <p className="text-[10px] text-red-600 mt-0.5">held at {train.held_by}</p>}
      </div>
    </div>
  )
}

function BlockCard({ block, exec, isOfficer, busy, onAction, onViewNotice }: {
  block: LiveBlock; exec?: any; isOfficer: boolean; busy: string; onAction: (a: string, p: number) => void; onViewNotice: (p: number) => void
}) {
  const stepIdx = EXEC_STEPS.indexOf(block.status)
  const label = block.status === 'SANCTIONED' ? 'Sanctioned' : block.status === 'IN_POSITION' ? 'Engineer on site' : block.status === 'BLOCK_ACTIVE' ? (block.active_now ? 'Active now' : 'Block active') : block.status === 'RELEASED' ? 'Released' : 'Completed'
  return (
    <div className={`rounded-xl border p-3 ${block.active_now ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'}`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-semibold text-gray-800 font-mono">{block.block_id}</p>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${block.active_now ? 'bg-red-500 text-white animate-pulse' : 'bg-blue-100 text-blue-700'}`}>
          {block.active_now ? '● LIVE' : label}
        </span>
      </div>
      <p className="text-xs text-gray-500">{block.maintenance_type} • {block.section}</p>
      <p className="text-xs font-mono text-gray-600 mt-0.5">Window {block.window} • V{block.version}</p>

      {block.status !== 'COMPLETED' && block.status !== 'RELEASED' && (
        <div className="flex items-center gap-1 mt-2">
          {EXEC_STEPS.map((s, i) => (
            <div key={s} className="flex items-center flex-1">
              <div className={`h-1.5 flex-1 rounded ${i <= stepIdx ? 'bg-blue-500' : 'bg-gray-200'}`} />
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        {!isOfficer && block.status === 'SANCTIONED' && (
          <button onClick={() => onAction('checkin', block.plan_id)} disabled={busy === `checkin:${block.plan_id}`}
            className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs hover:bg-blue-700 disabled:opacity-50">📍 Check In On Site</button>
        )}
        {!isOfficer && block.status === 'IN_POSITION' && (
          <button onClick={() => onAction('activate', block.plan_id)} disabled={busy === `activate:${block.plan_id}`}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs hover:bg-red-700 disabled:opacity-50">🛑 Activate Block</button>
        )}
        {!isOfficer && block.status === 'BLOCK_ACTIVE' && (
          <button onClick={() => onAction('release', block.plan_id)} disabled={busy === `release:${block.plan_id}`}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs hover:bg-emerald-700 disabled:opacity-50">✅ Release Line</button>
        )}
        {!isOfficer && block.status === 'RELEASED' && (
          <button onClick={() => onAction('complete', block.plan_id)} disabled={busy === `complete:${block.plan_id}`}
            className="px-3 py-1.5 rounded-lg bg-gray-700 text-white text-xs hover:bg-gray-800 disabled:opacity-50">🏁 Complete</button>
        )}
        <button onClick={() => onViewNotice(block.plan_id)} className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 text-xs hover:bg-gray-100">📄 Notice / CA</button>
      </div>
    </div>
  )
}

function ConflictCard({ conflict, isOfficer, onReplan, busy }: { conflict: LiveConflict; isOfficer: boolean; onReplan: () => void; busy: string }) {
  return (
    <div className={`rounded-xl border p-3 ${conflict.severity === 'HIGH' ? 'border-red-300 bg-red-50' : 'border-amber-200 bg-amber-50'}`}>
      <div className="flex items-center gap-2">
        <span className="text-red-600">🚨</span>
        <p className="text-sm font-semibold text-gray-800">{conflict.train_name}</p>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-so-red/15 text-so-red border border-so-red/30">{conflict.priority}</span>
      </div>
      <p className="text-xs text-gray-600 mt-1">
        Projected {conflict.projected_arrival} collides with <span className="font-semibold font-mono">{conflict.block_id}</span> ({conflict.window}). Delay {conflict.delay_minutes} min.
      </p>
      {isOfficer && conflict.auto_resolvable && (
        <button onClick={onReplan} disabled={busy.includes('dynamicReplan')}
          className="mt-2 w-full px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs hover:bg-amber-700 disabled:opacity-50">
          🔄 Trigger Dynamic Re-Plan (AI)
        </button>
      )}
    </div>
  )
}

function statusColor(s: string) {
  switch (s) {
    case 'APPROACHING': return 'bg-blue-100 text-blue-700'
    case 'IN_SECTION': return 'bg-amber-100 text-amber-700'
    case 'DEPARTED': return 'bg-gray-100 text-gray-500'
    default: return 'bg-gray-100 text-gray-400'
  }
}

function kindColor(k: string) {
  switch (k) {
    case 'SANCTIONED': return 'bg-blue-100 text-blue-700'
    case 'LATE_RUNNING': return 'bg-amber-100 text-amber-700'
    default: return 'bg-gray-100 text-gray-600'
  }
}