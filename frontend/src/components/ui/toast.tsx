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
          className={cn(
            'pointer-events-auto rounded-md px-4 py-2 text-sm shadow-lg ring-1 ring-inset',
            item.variant === 'success'
              ? 'bg-slate-900 text-white ring-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:ring-slate-300'
              : 'bg-red-600 text-white ring-red-700',
          )}
        >
          {item.message}
        </div>
      ))}
    </div>
  )
}
