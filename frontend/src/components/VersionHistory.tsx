import type { BlockPlan } from '../types'
import StatusBadge from './StatusBadge'

interface VersionHistoryProps {
  plans: BlockPlan[]
  currentVersion: number
}

export default function VersionHistory({ plans, currentVersion }: VersionHistoryProps) {
  const sorted = [...plans].sort((a, b) => b.version - a.version)

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 mb-6">
      <h3 className="font-semibold text-gray-900 mb-3 text-sm uppercase tracking-wide">Plan History</h3>
      <div className="space-y-3">
        {sorted.map((plan) => (
          <div
            key={plan.version}
            className={`flex items-center gap-4 p-3 rounded-md ${
              plan.version === currentVersion ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              plan.version === currentVersion ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
            }`}>
              V{plan.version}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{plan.start_time} - {plan.end_time}</span>
                <StatusBadge status={plan.status} />
                {plan.version === currentVersion && (
                  <span className="text-xs text-blue-600 font-medium">(Current)</span>
                )}
              </div>
              {plan.status === 'REJECTED' && (
                <p className="text-xs text-red-600 mt-0.5">Rejected - Replanning initiated</p>
              )}
              {plan.status === 'APPROVED' && plan.block_id && (
                <p className="text-xs text-green-600 mt-0.5">Published: {plan.block_id}</p>
              )}
            </div>
            <div className="text-right text-xs text-gray-500">
              <p>Risk: {plan.risk_score}</p>
              <p>{plan.estimated_delay_minutes} min delay</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
