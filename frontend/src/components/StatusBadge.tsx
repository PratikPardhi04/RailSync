const dot: Record<string, string> = {
  green: 'bg-so-green',
  amber: 'bg-so-amber',
  red: 'bg-so-red',
  blue: 'bg-so-cyan',
  violet: 'bg-so-violet',
  gray: 'bg-so-dim',
}

const statusConfig: Record<string, { dot: string; text: string; label: string }> = {
  DRAFT: { dot: 'gray', text: 'bg-so-dim/10 text-so-dim border-so-line2', label: 'Draft' },
  SUBMITTED: { dot: 'blue', text: 'bg-so-cyan/10 text-so-cyan border-so-cyan/30', label: 'Submitted' },
  PENDING: { dot: 'blue', text: 'bg-so-cyan/10 text-so-cyan border-so-cyan/30', label: 'Pending' },
  VALIDATING: { dot: 'amber', text: 'bg-so-amber/10 text-so-amber border-so-amber/30', label: 'Validating' },
  AI_ANALYSIS: { dot: 'violet', text: 'bg-so-violet/10 text-so-violet border-so-violet/30', label: 'AI Analysis' },
  OPTIMIZING: { dot: 'violet', text: 'bg-so-violet/10 text-so-violet border-so-violet/30', label: 'Optimizing' },
  SIMULATING: { dot: 'cyan', text: 'bg-so-cyan/10 text-so-cyan border-so-cyan/30', label: 'Simulating' },
  REPORT_READY: { dot: 'green', text: 'bg-so-green/10 text-so-green border-so-green/30', label: 'Report Ready' },
  AWAITING_OFFICER: { dot: 'amber', text: 'bg-so-amber/10 text-so-amber border-so-amber/30', label: 'Awaiting Officer' },
  REJECTED: { dot: 'red', text: 'bg-so-red/10 text-so-red border-so-red/30', label: 'Rejected' },
  REPLANNING: { dot: 'amber', text: 'bg-so-amber/10 text-so-amber border-so-amber/30', label: 'Replanning' },
  APPROVED: { dot: 'green', text: 'bg-so-green/10 text-so-green border-so-green/30', label: 'Approved' },
  PUBLISHED: { dot: 'green', text: 'bg-so-green/15 text-so-green border-so-green/40', label: 'Published' },
  FAILED: { dot: 'red', text: 'bg-so-red/10 text-so-red border-so-red/30', label: 'Failed' },
  PENDING_REVIEW: { dot: 'amber', text: 'bg-so-amber/10 text-so-amber border-so-amber/30', label: 'Pending Review' },
  GENERATED: { dot: 'blue', text: 'bg-so-cyan/10 text-so-cyan border-so-cyan/30', label: 'Generated' },
}

export default function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { dot: 'gray', text: 'bg-so-dim/10 text-so-dim border-so-line2', label: status }
  return (
    <span className={`chip border ${config.text}`}>
      <span className={`relative flex w-1.5 h-1.5 rounded-full ${dot[config.dot]}`}>
        {(status === 'AI_ANALYSIS' || status === 'OPTIMIZING' || status === 'SIMULATING') && (
          <span className={`absolute inset-0 rounded-full ${dot[config.dot]} animate-ping opacity-60`} />
        )}
      </span>
      {config.label}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    CRITICAL: 'bg-so-red/12 text-so-red border-so-red/35',
    HIGH: 'bg-so-amber/12 text-so-amber border-so-amber/35',
    MEDIUM: 'bg-so-cyan/12 text-so-cyan border-so-cyan/30',
    LOW: 'bg-so-green/12 text-so-green border-so-green/30',
  }
  return (
    <span className={`chip border ${colors[priority] || 'bg-so-dim/10 text-so-dim border-so-line2'}`}>
      {priority}
    </span>
  )
}

export function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-so-green/12 text-so-green border-so-green/30',
    MEDIUM: 'bg-so-amber/12 text-so-amber border-so-amber/30',
    HIGH: 'bg-so-red/12 text-so-red border-so-red/30',
    CRITICAL: 'bg-so-red/20 text-so-red border-so-red/40',
  }
  return (
    <span className={`chip border ${colors[level] || 'bg-so-dim/10 text-so-dim border-so-line2'}`}>
      {level}
    </span>
  )
}