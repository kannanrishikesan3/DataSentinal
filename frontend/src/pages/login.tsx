import { Shield } from 'lucide-react'
import * as React from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useLogin } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/lib/auth-context'

export function LoginPage() {
  const { isAuthenticated, refresh } = useAuth()
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')

  if (isAuthenticated) return <Navigate to="/" replace />

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          refresh()
          navigate('/')
        },
      },
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <Shield className="mb-2 h-8 w-8 text-slate-900 dark:text-slate-100" />
          <CardTitle className="text-lg text-slate-900 dark:text-slate-100">DataSentinel</CardTitle>
          <p className="text-xs text-slate-400">Discover. Classify. Protect.</p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="analyst@yourorg.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {login.isError && (
              <p className="text-sm text-red-600" role="alert">
                Invalid email or password.
              </p>
            )}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
