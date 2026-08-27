import { CheckCircle2, XCircle } from 'lucide-react'
import * as React from 'react'

import { cn } from '@/lib/utils'

interface Toast {
  id: number
  message: string
  variant: 'success' | 'error'
}

type Listener = (toasts: Toast[]) => void

let toasts: Toast[] = []
let nextId = 0
const listeners = new Set<Listener>()

function emit() {
  for (const listener of listeners) listener(toasts)
}

function pushToast(message: string, variant: Toast['variant']) {
  const id = nextId++
  toasts = [...toasts, { id, message, variant }]
  emit()
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    emit()
  }, 4000)
}

export const toast = {
  success: (message: string) => pushToast(message, 'success'),
  error: (message: string) => pushToast(message, 'error'),
}

export function Toaster() {
  const [items, setItems] = React.useState<Toast[]>(toasts)

  React.useEffect(() => {
    listeners.add(setItems)
    return () => {
      listeners.delete(setItems)
    }
  }, [])

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          role="status"
          className={cn(
            'pointer-events-auto flex items-center gap-2 rounded-md border px-4 py-2.5 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-2',
            item.variant === 'success'
              ? 'border-success/30 bg-success-bg text-success-fg'
              : 'border-destructive/30 bg-destructive/10 text-destructive',
          )}
        >
          {item.variant === 'success' ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 shrink-0" />
          )}
          {item.message}
        </div>
      ))}
    </div>
  )
}
