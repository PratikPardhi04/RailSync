import { useState, useEffect, useCallback } from 'react'
import type { User } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('raillink_user')
    if (stored) {
      try {
        setUser(JSON.parse(stored))
      } catch {
        localStorage.removeItem('raillink_user')
        localStorage.removeItem('raillink_token')
      }
    }
    setLoading(false)
  }, [])

  const login = useCallback((userData: User, token: string) => {
    setUser(userData)
    localStorage.setItem('raillink_user', JSON.stringify(userData))
    localStorage.setItem('raillink_token', token)
  }, [])

  const logout = useCallback(() => {
    setUser(null)
    localStorage.removeItem('raillink_user')
    localStorage.removeItem('raillink_token')
  }, [])

  return { user, login, logout, loading }
}
