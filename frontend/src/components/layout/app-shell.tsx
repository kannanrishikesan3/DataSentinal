import { LogOut } from 'lucide-react'
import { Outlet } from 'react-router-dom'

import { useCurrentUser } from '@/api/me'
import { Sidebar } from '@/components/layout/sidebar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'

export function AppShell() {
  const { logout } = useAuth()
  const { data: user } = useCurrentUser()

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {user && <span className="truncate">{user.email}</span>}
            {user && (
              <Badge variant="outline" className="shrink-0 capitalize">
                {user.role}
              </Badge>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
