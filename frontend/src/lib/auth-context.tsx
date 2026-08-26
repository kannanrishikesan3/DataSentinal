import * as React from 'react'

import { clearStoredToken, getStoredToken } from '@/lib/auth-storage'

interface AuthContextValue {
  isAuthenticated: boolean
  logout: () => void
  refresh: () => void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = React.useState(() => Boolean(getStoredToken()))

  const refresh = React.useCallback(() => {
    setIsAuthenticated(Boolean(getStoredToken()))
  }, [])

  const logout = React.useCallback(() => {
    clearStoredToken()
    setIsAuthenticated(false)
  }, [])

  const value = React.useMemo(() => ({ isAuthenticated, logout, refresh }), [isAuthenticated, logout, refresh])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = React.useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
