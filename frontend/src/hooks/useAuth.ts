import { useState, useEffect, useCallback } from 'react'
import type { User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('railsync_user')
    if (stored) {
      try {
        setUser(JSON.parse(stored))
      } catch {
        localStorage.removeItem('railsync_user')
        localStorage.removeItem('railsync_token')
      }
    }
    setLoading(false)
  }, [])

  const login = useCallback((userData: User, token: string) => {
    setUser(userData)
    localStorage.setItem('railsync_user', JSON.stringify(userData))
    localStorage.setItem('railsync_token', token)
  }, [])

  const logout = useCallback(() => {
    setUser(null)
    localStorage.removeItem('railsync_user')
    localStorage.removeItem('railsync_token')
  }, [])

  return { user, login, logout, loading }
}
