import {
  Cpu,
  FileSearch,
  FileText,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
  Shield,
  Users,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { Logo } from '@/components/logo'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/endpoints', label: 'Endpoints', icon: Cpu, end: false },
  { to: '/scans', label: 'Scans', icon: ListChecks, end: false },
  { to: '/findings', label: 'Findings', icon: FileSearch, end: false },
  { to: '/pii-explorer', label: 'PII Explorer', icon: Users, end: false },
  { to: '/secrets', label: 'Secrets', icon: KeyRound, end: false },
  { to: '/policies', label: 'Policies', icon: Shield, end: false },
  { to: '/reports', label: 'Reports', icon: FileText, end: false },
  { to: '/audit-logs', label: 'Audit Logs', icon: ScrollText, end: false },
  { to: '/settings', label: 'Settings', icon: Settings, end: false },
] as const

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2.5 border-b border-sidebar-border px-4 py-4">
        <Logo className="h-6 w-6 shrink-0 text-sidebar-accent-foreground" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold leading-none text-sidebar-foreground">DataSentinel</p>
          <p className="mt-1 truncate text-[11px] leading-none text-sidebar-muted-foreground">
            Discover. Classify. Protect.
          </p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/40 hover:text-sidebar-foreground',
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
