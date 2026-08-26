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
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
        <Shield className="h-5 w-5 text-slate-900 dark:text-slate-100" />
        <div>
          <p className="text-sm font-semibold leading-none text-slate-900 dark:text-slate-100">DataSentinel</p>
          <p className="text-[11px] leading-none text-slate-400">Discover. Classify. Protect.</p>
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
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800',
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
