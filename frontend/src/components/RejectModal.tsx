import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface RejectModalProps {
  open: boolean
  onClose: () => void
  onSubmit: (reason: string, avoidTime?: string, preferred?: string, constraint?: string) => void
}

export default function RejectModal({ open, onClose, onSubmit }: RejectModalProps) {
  const [reason, setReason] = useState('')
  const [avoidTime, setAvoidTime] = useState('')
  const [preferred, setPreferred] = useState('')
  const [constraint, setConstraint] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!reason.trim()) return
    setSubmitting(true)
    try {
      await onSubmit(reason, avoidTime || undefined, preferred || undefined, constraint || undefined)
      setReason('')
      setAvoidTime('')
      setPreferred('')
      setConstraint('')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative bg-white rounded-lg shadow-xl w-full max-w-lg p-6 mx-4"
          >
            <h2 className="text-lg font-bold text-gray-900 mb-1">Reject Block Plan</h2>
            <p className="text-sm text-gray-500 mb-4">Provide a reason for rejection. The AI will use this feedback to regenerate the plan.</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rejection Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm"
                  placeholder="e.g., Important passenger train affected. Avoid 10:00-13:00."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Time (optional)</label>
                  <input
                    type="text"
                    value={preferred}
                    onChange={(e) => setPreferred(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                    placeholder="e.g., After 13:00"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Avoid Time (optional)</label>
                  <input
                    type="text"
                    value={avoidTime}
                    onChange={(e) => setAvoidTime(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                    placeholder="e.g., 10:00-13:00"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Additional Constraint (optional)</label>
                <input
                  type="text"
                  value={constraint}
                  onChange={(e) => setConstraint(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                  placeholder="e.g., No freight train disruption"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!reason.trim() || submitting}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Rejecting...' : 'Reject & Replan'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
