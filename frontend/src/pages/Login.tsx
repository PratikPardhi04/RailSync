import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { auth } from '../services/api'
import { motion } from 'framer-motion'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await auth.login(email, password)
      login(res.user, res.access_token)
      navigate(res.user.role === 'officer' ? '/officer' : '/engineer')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const quickLogin = async (role: string) => {
    setError('')
    setLoading(true)
    try {
      const email = role === 'engineer' ? 'engineer@raillink.in' : 'officer@raillink.in'
      const pass = role === 'engineer' ? 'engineer123' : 'officer123'
      const res = await auth.login(email, pass)
      login(res.user, res.access_token)
      navigate(role === 'officer' ? '/officer' : '/engineer')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-railway-darkblue flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-lg shadow-xl w-full max-w-md p-8"
      >
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-railway-blue rounded-full mb-4">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-railway-blue">RailLink AI</h1>
          <p className="text-sm text-railway-muted mt-1">Railway Maintenance Block Planning System</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-railway-accent focus:border-transparent"
              placeholder="Enter your email"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-railway-accent focus:border-transparent"
              placeholder="Enter your password"
              required
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-railway-blue text-white py-2 px-4 rounded-md hover:bg-railway-darkblue transition-colors disabled:opacity-50 font-medium"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-xs text-center text-gray-500 mb-3">Quick Demo Access</p>
          <div className="flex gap-3">
            <button
              onClick={() => quickLogin('engineer')}
              disabled={loading}
              className="flex-1 bg-[#18794E] text-white py-2 px-3 rounded-md hover:bg-[#125F3E] transition-colors text-sm font-medium disabled:opacity-50"
            >
              Login as Engineer
            </button>
            <button
              onClick={() => quickLogin('officer')}
              disabled={loading}
              className="flex-1 bg-railway-accent text-white py-2 px-3 rounded-md hover:bg-railway-darkblue transition-colors text-sm font-medium disabled:opacity-50"
            >
              Login as Officer
            </button>
          </div>
        </div>

        <p className="text-xs text-center text-gray-400 mt-4">
          Demo Mode - Prototype / Simulated Data
        </p>
      </motion.div>
    </div>
  )
}
