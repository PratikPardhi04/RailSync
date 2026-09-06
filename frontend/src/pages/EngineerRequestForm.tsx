import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ClipboardList, Wrench, HardHat, Settings2, Paperclip, Send,
  Check, ChevronLeft, ChevronRight, UploadCloud, File, X, Loader2, TrendingUp,
} from 'lucide-react'
import Layout from '../components/Layout'
import { requests } from '../services/api'
import type { MaintenanceRequestCreate, AttachmentMeta } from '../types'

interface StepDef {
  id: number
  title: string
  blurb: string
  icon: React.ComponentType<{ className?: string }>
}

const STEPS: StepDef[] = [
  { id: 1, title: 'Basic Info', blurb: 'Who, where, what asset', icon: ClipboardList },
  { id: 2, title: 'Maintenance', blurb: 'Work + schedule window', icon: Wrench },
  { id: 3, title: 'Resources', blurb: 'Machines, crew, workforce', icon: HardHat },
  { id: 4, title: 'Operations', blurb: 'Track, block, restrictions', icon: Settings2 },
  { id: 5, title: 'Attachments', blurb: 'Permits & inspection reports', icon: Paperclip },
  { id: 6, title: 'Review & Submit', blurb: 'Confirm and launch AI', icon: Send },
]

interface WizForm {
  department: string
  division: string
  section: string
  location_km: string
  asset_id: string
  maintenance_type: string
  priority: string
  description: string
  reason: string
  requested_date: string
  preferred_start: string
  duration_minutes: number
  machines: string
  equipment: string
  crew_size: number
  estimated_workforce: number
  est_material_cost?: number
  weather_sensitive: string
  track_line: string
  block_type: string
  direction: string
  isolation_required: string
  expected_operational_impact: string
  priority_train_restrictions: string
  attachments: AttachmentMeta[]
}

type SubmitPhase = 'idle' | 'creating' | 'sending' | 'launching' | 'done'

const todayISO = () => new Date().toISOString().split('T')[0]
const tomorrowISO = () => new Date(Date.now() + 86400000).toISOString().split('T')[0]

function addMinutes(time: string, mins: number): string {
  const [h, m] = (time || '00:00').split(':').map(Number)
  const total = (h * 60 + m + mins) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function formatBytes(b: number): string {
  if (b >= 1048576) return `${(b / 1048576).toFixed(1)} MB`
  if (b >= 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${b} B`
}

const inputCls =
  'w-full px-3.5 py-2.5 rounded-lg bg-white border border-so-line2 text-so-text text-sm ' +
  'placeholder:text-so-dim/70 focus:outline-none focus:ring-2 focus:ring-so-cyan/50 focus:border-so-cyan/60 transition-all'
const labelCls = 'block text-[11px] font-semibold uppercase tracking-wider text-so-dim mb-1.5'
const errorCls = 'text-xs text-so-red mt-1.5'

function Field({ label, required, error, children, hint }: {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className={labelCls}>
        {label}
        {required && <span className="text-so-red ml-0.5">*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-[11px] text-so-dim/80 mt-1">{hint}</p>}
      {error && <p className={errorCls}>{error}</p>}
    </div>
  )
}

function reviewGroup(title: string, icon: React.ComponentType<{ className?: string }>, rows: [string, React.ReactNode][]) {
  const Icon = icon
  return (
    <div className="glass-deep rounded-2xl p-5 border border-so-line2">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-so-cyan" />
        <h4 className="font-bold text-so-text text-sm tracking-wide">{title}</h4>
      </div>
      {rows.map(([k, v], i) => (
        <div key={i} className="kv">
          <span className="text-so-dim">{k}</span>
          <span className="text-so-text font-semibold text-right">{v ?? '—'}</span>
        </div>
      ))}
    </div>
  )
}

export default function EngineerRequestForm() {
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState(1)
  const [completed, setCompleted] = useState<number[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [dragActive, setDragActive] = useState(false)

  const [form, setForm] = useState<WizForm>(() => ({
    department: 'Engineering',
    division: 'Pune Division',
    section: 'Shivajinagar - Khadki',
    location_km: 'KM 128/600 - 129/200 (Down Main, turnout 42 approach)',
    asset_id: 'BFT-1285-OW',
    maintenance_type: 'Track Maintenance',
    priority: 'HIGH',
    description: 'Deep ballast renewal and rail-pad replacement on the busy Down Main between Shivajinagar and Khadki. High axle-load corridor traffic has accelerated wear on turnout 42 approach; renewal is required before the monsoon.',
    reason: 'Track geometry measurements at KM 128/800 exceeded maintenance limits (alignment +7 mm, twist exceedance). This section carries the full Pune - Mumbai corridor (30+ trains/day including premium services), so the renewal cannot be postponed.',
    requested_date: tomorrowISO(),
    preferred_start: '10:00',
    duration_minutes: 120,
    machines: 'Tamping machine + ballast regulator',
    equipment: 'Tower wagon, rail cutter, hydraulic jacks, rail pads',
    crew_size: 12,
    estimated_workforce: 12,
    weather_sensitive: 'NO',
    track_line: 'Down Main Line',
    block_type: 'MAINTENANCE BLOCK',
    direction: 'UP',
    isolation_required: 'NO',
    expected_operational_impact: 'Likely to affect multiple express and passenger trains; AI should select the least-impact window and propose rerouting via the Yerwada diversion where feasible.',
    priority_train_restrictions: 'Do not delay Mumbai Rajdhani, Shatabdi or Vande Bharat beyond 10 min.',
    attachments: [],
  }))

  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>('idle')
  const [submitError, setSubmitError] = useState('')
  const [createdId, setCreatedId] = useState<number | null>(null)

  const update = (field: keyof WizForm, value: string | number | undefined | AttachmentMeta[]) => {
    setForm(prev => ({ ...prev, [field]: value as never }))
  }

  function validateStep(s: number, f: WizForm): string[] {
    const errs: string[] = []
    switch (s) {
      case 1:
        if (!f.department.trim()) errs.push('Department is required')
        if (!f.division.trim()) errs.push('Division is required')
        if (!f.section.trim()) errs.push('Section is required')
        if (!f.location_km.trim()) errs.push('Location / KM range is required')
        break
      case 2:
        if (!f.maintenance_type.trim()) errs.push('Maintenance type is required')
        if (!f.priority) errs.push('Priority is required')
        if (!f.description.trim()) errs.push('Description is required')
        if (!f.reason.trim()) errs.push('Reason / justification is required')
        if (!f.requested_date) errs.push('Requested date is required')
        if (!f.preferred_start) errs.push('Preferred start time is required')
        if (!f.duration_minutes || f.duration_minutes < 30) errs.push('Required duration must be at least 30 minutes')
        break
      case 3:
        if (!f.crew_size || f.crew_size < 1) errs.push('Crew required is required (minimum 1)')
        if (!f.estimated_workforce || f.estimated_workforce < 1) errs.push('Estimated workforce must be at least 1')
        break
      case 4:
        if (!f.track_line.trim()) errs.push('Track / Line is required')
        if (!f.block_type) errs.push('Block type is required')
        if (!f.direction) errs.push('Direction is required')
        if (!f.isolation_required) errs.push('Isolation requirement is required')
        break
      case 5:
        break
    }
    return errs
  }

  const goBack = () => { setErrors([]); if (step > 1) setStep(step - 1) }
  const goNext = () => {
    const errs = validateStep(step, form)
    if (errs.length) { setErrors(errs); return }
    setErrors([])
    setCompleted(prev => prev.includes(step) ? prev : [...prev, step])
    setStep(step + 1)
  }

  const handleFiles = (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return
    const metas: AttachmentMeta[] = Array.from(files)
      .filter(f => f.size > 0)
      .map(f => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name,
        size: f.size,
        sizeLabel: formatBytes(f.size),
        type: f.type || f.name.split('.').pop() || 'file',
      }))
    setForm(prev => ({ ...prev, attachments: [...prev.attachments, ...metas] }))
  }

  const removeAttachment = (id: string) => {
    setForm(prev => ({ ...prev, attachments: prev.attachments.filter(a => a.id !== id) }))
  }

  function composeInstructions(f: WizForm): string {
    const parts = [
      `Block: ${f.block_type}${f.track_line ? `, Track ${f.track_line}` : ''}`,
      `Direction: ${f.direction}`,
      `Isolation required: ${f.isolation_required}`,
      f.expected_operational_impact ? `Expected operational impact: ${f.expected_operational_impact}` : '',
      f.priority_train_restrictions ? `Priority train restrictions: ${f.priority_train_restrictions}` : '',
      f.asset_id ? `Asset ID: ${f.asset_id}` : '',
      f.location_km ? `Location / KM: ${f.location_km}` : '',
    ].filter(Boolean)
    return parts.join('. ')
  }

  async function handleSubmit() {
    setSubmitError('')
    setSubmitPhase('creating')
    try {
      const payload: MaintenanceRequestCreate = {
        department: form.department,
        maintenance_type: form.maintenance_type,
        location: form.division,
        section: form.section,
        requested_date: form.requested_date,
        preferred_start: form.preferred_start,
        preferred_end: addMinutes(form.preferred_start, form.duration_minutes),
        duration_minutes: form.duration_minutes,
        priority: form.priority,
        description: form.description.trim() || 'Maintenance block request',
        work_type: form.maintenance_type,
        track_no: form.track_line.trim() || undefined,
        equipment: [form.machines, form.equipment].map(s => s.trim()).filter(Boolean).join(', ') || undefined,
        crew_size: form.crew_size || 1,
        est_material_cost: form.est_material_cost ?? undefined,
        weather_sensitive: form.weather_sensitive,
        special_instructions: composeInstructions(form),
        request_metadata: {
          division: form.division,
          location_km: form.location_km,
          asset_id: form.asset_id,
          reason: form.reason,
          machines: form.machines,
          estimated_workforce: form.estimated_workforce,
          track_line: form.track_line,
          block_type: form.block_type,
          direction: form.direction,
          isolation_required: form.isolation_required,
          expected_operational_impact: form.expected_operational_impact,
          priority_train_restrictions: form.priority_train_restrictions,
          attachments: form.attachments.map(({ id, name, size, sizeLabel, type }) => ({ id, name, size, sizeLabel, type })),
        },
      }

      const res = await requests.create(payload)
      setCreatedId(res.id)
      setSubmitPhase('sending')

      await new Promise(r => setTimeout(r, 700))
      setSubmitPhase('done')
      navigate(`/engineer/request/${res.id}`)
    } catch (err: any) {
      setSubmitError(err?.message || 'Failed to submit request')
      setSubmitPhase('idle')
    }
  }

  const preferredEnd = addMinutes(form.preferred_start, form.duration_minutes || 0)
  const activeComp = STEPS[step - 1]

  return (
    <Layout title="Raise Block Request" subtitle="6-step wizard · submitted directly to the RailLink AI / LangGraph pipeline">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* stepper */}
        <div className="flex items-start overflow-x-auto pb-1">
          {STEPS.map((s, i) => {
            const done = completed.includes(s.id) || s.id < step
            const active = s.id === step && submitPhase === 'idle'
            return (
              <div key={s.id} className="flex items-start flex-1 min-w-[92px] last:flex-none">
                {i > 0 && (
                  <div className={`mt-5 flex-1 min-w-[16px] h-px ${completed.includes(s.id - 1) ? 'bg-so-green/50' : 'bg-so-line'}`} />
                )}
                <div className="flex flex-col items-center gap-1.5 px-1.5 w-full">
                  <div
                    className={`w-10 h-10 rounded-xl border flex items-center justify-center transition-all ${
                      done && !active
                        ? 'bg-so-green/15 border-so-green/40 text-so-green'
                        : active
                          ? 'bg-so-cyan/15 border-so-cyan/60 text-so-cyan shadow-glow'
                          : 'bg-so-panel border-so-line text-so-dim'
                    }`}
                  >
                    {done && !active ? <Check className="w-5 h-5" strokeWidth={3} /> : <s.icon className="w-5 h-5" />}
                  </div>
                  <div className="hidden sm:block text-center">
                    <p className={`text-[11px] font-bold tracking-wide truncate max-w-full ${
                      active ? 'text-so-cyan' : done ? 'text-so-text' : 'text-so-dim'
                    }`}>
                      {s.title}
                    </p>
                    <p className="text-[10px] text-so-dim truncate">{s.blurb}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {submitPhase === 'idle' ? (
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="glass-deep rounded-2xl border border-so-line2 overflow-hidden"
          >
            <div className="h-0.5 bg-so-cyan" />
            <div className="px-6 py-5 border-b border-so-line flex items-center gap-3">
              <div className={`w-9 h-9 rounded-xl border flex items-center justify-center ${
                step === 6 ? 'bg-so-green/15 border-so-green/40 text-so-green' : 'bg-so-cyan/15 border-so-cyan/40 text-so-cyan'
              }`}>
                <activeComp.icon className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-so-text">
                  Step {step} of 6 — {activeComp.title}
                </h3>
                <p className="text-xs text-so-dim">{activeComp.blurb}</p>
              </div>
              <div className="ml-auto text-[11px] font-mono text-so-dim">
                {step < 6 ? `Request ID generated on submission` : createdId ? `MR-${String(createdId).padStart(5, '0')}` : 'New request'}
              </div>
            </div>

            <div className="p-6">
              {errors.length > 0 && (
                <div className="mb-5 rounded-xl bg-so-red/10 border border-so-red/30 px-4 py-3">
                  <p className="text-xs font-semibold text-so-red mb-1">Please fix the following before continuing:</p>
                  <ul className="list-disc list-inside text-xs text-so-text space-y-0.5">
                    {errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}

              {/* STEP 1 — BASIC INFO */}
              {step === 1 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <Field label="Request ID" hint="Auto-generated on submission">
                    <div className="relative">
                      <input type="text" disabled value="" placeholder="MR-XXXXX · auto" className={`${inputCls} opacity-70 cursor-not-allowed`} />
                    </div>
                  </Field>
                  <Field label="Department" required>
                    <select value={form.department} onChange={e => update('department', e.target.value)} className={inputCls}>
                      <option>Engineering</option>
                      <option>S&T</option>
                      <option>Traction</option>
                      <option>Electrical</option>
                    </select>
                  </Field>
                  <Field label="Division" required>
                    <select value={form.division} onChange={e => update('division', e.target.value)} className={inputCls}>
                      <option>Pune Division</option>
                      <option>Mumbai Division</option>
                      <option>Nagpur Division</option>
                      <option>Hyderabad Division</option>
                    </select>
                  </Field>
                  <Field label="Section" required>
                    <input type="text" value={form.section} onChange={e => update('section', e.target.value)} placeholder="e.g. Shivajinagar - Khadki" className={inputCls} />
                  </Field>
                  <Field label="Location / KM range" required hint="e.g. KM 142.3 – 142.9, DN line">
                    <input type="text" value={form.location_km} onChange={e => update('location_km', e.target.value)} placeholder="e.g. KM 142.3 – 142.9" className={inputCls} />
                  </Field>
                  <Field label="Asset ID" hint="Track section / structure ID if known (optional)">
                    <input type="text" value={form.asset_id} onChange={e => update('asset_id', e.target.value)} placeholder="e.g. TRK-142-DN / BR-07" className={inputCls} />
                  </Field>
                </div>
              )}

              {/* STEP 2 — MAINTENANCE */}
              {step === 2 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <Field label="Maintenance Type" required>
                    <select value={form.maintenance_type} onChange={e => update('maintenance_type', e.target.value)} className={inputCls}>
                      <option>Track Maintenance</option>
                      <option>Signal Maintenance</option>
                      <option>Electrical Maintenance</option>
                      <option>OHE Maintenance</option>
                      <option>Bridge Inspection</option>
                      <option>Track Reconditioning</option>
                    </select>
                  </Field>
                  <Field label="Priority" required>
                    <select value={form.priority} onChange={e => update('priority', e.target.value)} className={inputCls}>
                      <option value="CRITICAL">CRITICAL</option>
                      <option value="HIGH">HIGH</option>
                      <option value="MEDIUM">MEDIUM</option>
                      <option value="LOW">LOW</option>
                    </select>
                  </Field>
                  <div className="sm:col-span-2">
                    <Field label="Description" required>
                      <textarea value={form.description} onChange={e => update('description', e.target.value)} rows={3} className={`${inputCls} resize-y`} placeholder="Describe the maintenance work required..." />
                    </Field>
                  </div>
                  <div className="sm:col-span-2">
                    <Field label="Reason / Justification" required>
                      <textarea value={form.reason} onChange={e => update('reason', e.target.value)} rows={2} className={`${inputCls} resize-y`} placeholder="Why is this work required now? Asset condition, inspection findings, safety..." />
                    </Field>
                  </div>
                  <Field label="Requested Date" required>
                    <input type="date" min={todayISO()} value={form.requested_date} onChange={e => update('requested_date', e.target.value)} className={inputCls} />
                  </Field>
                  <div>
                    <Field label="Preferred Start Time" required>
                      <input type="time" value={form.preferred_start} onChange={e => update('preferred_start', e.target.value)} className={inputCls} />
                    </Field>
                  </div>
                  <Field label="Required Duration (minutes)" required hint={`≈ ${(form.duration_minutes / 60).toFixed(1).replace(/\.0$/, '')} h · ends ${preferredEnd}`}>
                    <input type="number" min={30} max={600} step={15} value={form.duration_minutes} onChange={e => update('duration_minutes', parseInt(e.target.value) || 0)} className={inputCls} />
                  </Field>
                </div>
              )}

              {/* STEP 3 — RESOURCES */}
              {step === 3 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <Field label="Machines Required" hint="e.g. Tower wagon, tamping machine, crane">
                    <input type="text" value={form.machines} onChange={e => update('machines', e.target.value)} placeholder="e.g. Tower wagon, tamping machine" className={inputCls} />
                  </Field>
                  <Field label="Equipment Required" hint="e.g. Track tools, NDT gear, lighting">
                    <input type="text" value={form.equipment} onChange={e => update('equipment', e.target.value)} placeholder="e.g. NDT gear, power tools" className={inputCls} />
                  </Field>
                  <Field label="Crew Required" required>
                    <input type="number" min={1} value={form.crew_size} onChange={e => update('crew_size', parseInt(e.target.value) || 0)} className={inputCls} />
                  </Field>
                  <Field label="Estimated Workforce" required hint="Total staff incl. supervisors & safety">
                    <input type="number" min={1} value={form.estimated_workforce} onChange={e => update('estimated_workforce', parseInt(e.target.value) || 0)} className={inputCls} />
                  </Field>
                  <Field label="Est. Material Cost (₹)" hint="Optional — used for cost estimate">
                    <input type="number" min={0} step={500} value={form.est_material_cost ?? ''} onChange={e => update('est_material_cost', e.target.value === '' ? undefined : parseFloat(e.target.value))} placeholder="e.g. 25000" className={inputCls} />
                  </Field>
                  <Field label="Weather Sensitive?">
                    <select value={form.weather_sensitive} onChange={e => update('weather_sensitive', e.target.value)} className={inputCls}>
                      <option value="NO">No</option>
                      <option value="YES">Yes</option>
                    </select>
                  </Field>
                </div>
              )}

              {/* STEP 4 — OPERATIONS */}
              {step === 4 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <Field label="Track / Line" required hint="Working line affected">
                    <input type="text" value={form.track_line} onChange={e => update('track_line', e.target.value)} placeholder="e.g. DN-2 / Metro line 3" className={inputCls} />
                  </Field>
                  <Field label="Block Type" required>
                    <select value={form.block_type} onChange={e => update('block_type', e.target.value)} className={inputCls}>
                      <option>MAINTENANCE BLOCK</option>
                      <option>TRACK POSSESSION</option>
                      <option>FOOTPLATE INSPECTION</option>
                      <option>SPEED RESTRICTION</option>
                    </select>
                  </Field>
                  <Field label="Direction" required>
                    <select value={form.direction} onChange={e => update('direction', e.target.value)} className={inputCls}>
                      <option>UP</option>
                      <option>DN</option>
                      <option>BOTH</option>
                    </select>
                  </Field>
                  <Field label="Isolation Required" required hint="Power / traction isolation">
                    <select value={form.isolation_required} onChange={e => update('isolation_required', e.target.value)} className={inputCls}>
                      <option value="NO">No</option>
                      <option value="YES">Yes</option>
                    </select>
                  </Field>
                  <Field label="Expected Operational Impact" hint="Anticipated effect on train movement">
                    <select value={form.expected_operational_impact} onChange={e => update('expected_operational_impact', e.target.value)} className={inputCls}>
                      <option value="">Select expected impact...</option>
                      <option>Minimal — low traffic window</option>
                      <option>Minor delays expected</option>
                      <option>Rerouting / cascade delays</option>
                      <option>Major — cancellations possible</option>
                    </select>
                  </Field>
                  <Field label="Priority Train Restrictions" hint="e.g. No Rajdhani/Shatabdi 30 min before/after">
                    <input type="text" value={form.priority_train_restrictions} onChange={e => update('priority_train_restrictions', e.target.value)} placeholder="e.g. Protect Rajdhani/Shatabdi windows" className={inputCls} />
                  </Field>
                </div>
              )}

              {/* STEP 5 — ATTACHMENTS */}
              {step === 5 && (
                <div className="space-y-4">
                  <div
                    onDragOver={e => { e.preventDefault(); setDragActive(true) }}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={e => { e.preventDefault(); setDragActive(false); handleFiles(e.dataTransfer.files) }}
                    onClick={() => fileInput.current?.click()}
                    className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
                      dragActive ? 'border-so-cyan/70 bg-so-cyan/10' : 'border-so-line2 bg-so-panel/60 hover:border-so-cyan/50'
                    }`}
                  >
                    <UploadCloud className="w-9 h-9 mx-auto mb-3 text-so-cyan" />
                    <p className="text-sm font-semibold text-so-text">Drag &amp; drop files here</p>
                    <p className="text-xs text-so-dim mt-1">
                      or <span className="text-so-cyan underline underline-offset-2">browse</span> — PDF, images, work permits, inspection reports
                    </p>
                    <input
                      ref={fileInput}
                      type="file"
                      multiple
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,application/pdf,image/*"
                      className="hidden"
                      onChange={e => { handleFiles(e.target.files); e.target.value = '' }}
                    />
                  </div>

                  {form.attachments.length > 0 && (
                    <div className="space-y-2">
                      <p className="h-overline">UPLOADED FILES — {form.attachments.length}</p>
                      {form.attachments.map(a => (
                        <div key={a.id} className="flex items-center gap-3 rounded-xl border border-so-line2 bg-so-panel/60 px-4 py-3">
                          <File className="w-5 h-5 text-so-cyan shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm text-so-text truncate">{a.name}</p>
                            <p className="text-[11px] text-so-dim">{a.sizeLabel} · {a.type}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeAttachment(a.id)}
                            className="p-1.5 rounded-lg text-so-dim hover:text-so-red hover:bg-so-red/10 transition-colors"
                            aria-label={`Remove ${a.name}`}
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {form.attachments.length === 0 && (
                    <p className="text-xs text-so-dim text-center">
                      No attachments yet — you can continue without them, or add work permits / inspection reports now.
                    </p>
                  )}
                </div>
              )}

              {/* STEP 6 — REVIEW & SUBMIT */}
              {step === 6 && (
                <div className="space-y-5">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {reviewGroup('Basic Information', ClipboardList, [
                      ['Request ID', createdId ? `MR-${String(createdId).padStart(5, '0')}` : 'Auto-generated on submission'],
                      ['Department', form.department],
                      ['Division', form.division],
                      ['Section', form.section],
                      ['Location / KM', form.location_km],
                      ['Asset ID', form.asset_id || '—'],
                    ])}
                    {reviewGroup('Maintenance Details', Wrench, [
                      ['Maintenance Type', form.maintenance_type],
                      ['Priority', form.priority],
                      ['Requested Date', form.requested_date],
                      ['Preferred Start', `${form.preferred_start} – ${preferredEnd}`],
                      ['Duration', `${form.duration_minutes} min (${(form.duration_minutes / 60).toFixed(1).replace(/\.0$/, '')} h)`],
                      ['Description', form.description],
                      ['Reason', form.reason],
                    ])}
                    {reviewGroup('Resources', HardHat, [
                      ['Machines', form.machines || '—'],
                      ['Equipment', form.equipment || '—'],
                      ['Crew Required', `${form.crew_size} staff`],
                      ['Estimated Workforce', `${form.estimated_workforce} staff`],
                      ['Est. Material Cost', form.est_material_cost != null ? `₹${form.est_material_cost.toLocaleString('en-IN')}` : '—'],
                      ['Weather Sensitive', form.weather_sensitive],
                    ])}
                    {reviewGroup('Operational Requirements', Settings2, [
                      ['Track / Line', form.track_line],
                      ['Block Type', form.block_type],
                      ['Direction', form.direction],
                      ['Isolation Required', form.isolation_required],
                      ['Operational Impact', form.expected_operational_impact || '—'],
                      ['Priority Train Restrictions', form.priority_train_restrictions || '—'],
                    ])}
                    {reviewGroup('Attachments', Paperclip, [
                      ['Files', form.attachments.length ? form.attachments.map(a => a.name).join(', ') : 'None'],
                      ['Total Size', form.attachments.length ? form.attachments.reduce((s, a) => s + a.size, 0) > 0 ? `${(form.attachments.reduce((s, a) => s + a.size, 0) / 1048576).toFixed(2)} MB` : '0 B' : '—'],
                    ])}
                  </div>

                  <div className="rounded-xl border border-so-cyan/30 bg-so-cyan/10 px-5 py-4">
                    <p className="text-xs font-semibold text-so-cyan flex items-center gap-2">
                      <TrendingUp className="w-4 h-4" /> Submitting will create the request and immediately send it to the RailLink AI / LangGraph planning pipeline.
                    </p>
                    <p className="text-xs text-so-dim mt-1">
                      A LangGraph run will validate data, retrieve RAG &amp; web evidence, run CP-SAT optimization, simulate train impact, and gate results — then produce a classified plan report. You will land on the live pipeline view.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* footer nav */}
            <div className="px-6 py-4 border-t border-so-line flex items-center justify-between gap-3">
              <div>
                {step === 1 ? (
                  <button type="button" onClick={() => navigate('/engineer')} className="btn-ghost">
                    Cancel
                  </button>
                ) : (
                  <button type="button" onClick={goBack} className="btn-ghost inline-flex items-center gap-1.5">
                    <ChevronLeft className="w-4 h-4" /> Back
                  </button>
                )}
              </div>
              {step < 6 ? (
                <button type="button" onClick={goNext} className="btn-rail inline-flex items-center gap-1.5">
                  Continue <ChevronRight className="w-4 h-4" />
                </button>
              ) : (
                <button type="button" onClick={handleSubmit} className="btn-rail inline-flex items-center gap-2 px-7">
                  <Send className="w-4 h-4" /> Submit for AI Optimization
                </button>
              )}
            </div>
          </motion.div>
        ) : (
          /* submission progress overlay */
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-deep rounded-2xl border border-so-line2 overflow-hidden">
            <div className="h-0.5 bg-so-green" />
            <div className="p-8 max-w-lg mx-auto text-center">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-so-cyan/10 border border-so-line2 flex items-center justify-center mb-5">
                {submitPhase === 'done' ? (
                  <Check className="w-7 h-7 text-so-green" strokeWidth={3} />
                ) : (
                  <Loader2 className="w-7 h-7 text-so-cyan animate-spin" />
                )}
              </div>
              <h3 className="text-so-text font-bold text-lg">
                {submitPhase === 'done' ? 'Workflow launched' : 'Submitting to RailLink AI'}
              </h3>
              <p className="text-xs text-so-dim mt-1 mb-6">
                {createdId ? `Request MR-${String(createdId).padStart(5, '0')} being routed into the LangGraph pipeline` : 'Connecting to the planning service…'}
              </p>

              <div className="text-left space-y-3">
                {[
                  { key: 'creating', label: 'Creating maintenance request' },
                  { key: 'sending', label: 'Request recorded & status set to PENDING' },
                  { key: 'launching', label: 'Opening pipeline — analysis auto-starts' },
                  { key: 'done', label: 'Opening live pipeline view' },
                ].map(item => {
                  const idx = ['creating', 'sending', 'launching', 'done'].indexOf(item.key)
                  const cur = ['creating', 'sending', 'launching', 'done'].indexOf(submitPhase)
                  const state = cur > idx ? 'done' : cur === idx ? 'active' : 'todo'
                  return (
                    <div key={item.key} className="flex items-center gap-3">
                      <div className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${
                        state === 'done' ? 'bg-so-green/15 border-so-green/40 text-so-green'
                        : state === 'active' ? 'bg-so-cyan/15 border-so-cyan/60 text-so-cyan'
                        : 'bg-so-panel border-so-line text-so-dim'
                      }`}>
                        {state === 'done' ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : <span className="text-[10px] font-bold">{idx + 1}</span>}
                      </div>
                      <p className={`text-sm ${state === 'done' ? 'text-so-text' : state === 'active' ? 'text-so-cyan font-semibold' : 'text-so-dim'}`}>
                        {item.label}
                      </p>
                      {state === 'active' && <Loader2 className="w-3.5 h-3.5 text-so-cyan animate-spin ml-auto" />}
                    </div>
                  )
                })}
              </div>

              {submitError && (
                <div className="mt-6 rounded-xl bg-so-red/10 border border-so-red/30 px-4 py-3">
                  <p className="text-xs text-so-red font-semibold mb-2">{submitError}</p>
                  <div className="flex gap-2 justify-center">
                    <button onClick={() => { setSubmitError(''); setSubmitPhase('idle') }} className="btn-ghost text-xs">Back to form</button>
                    <button onClick={handleSubmit} className="btn-rail text-xs">Retry</button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  )
}