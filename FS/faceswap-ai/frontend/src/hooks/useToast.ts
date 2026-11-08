import * as React from 'react'

type ToastVariant = 'default' | 'success' | 'destructive' | 'warning'

interface ToastData {
  id: string
  title: string
  description?: string
  variant?: ToastVariant
  duration?: number
}

interface ToastState {
  toasts: ToastData[]
}

type ToastAction =
  | { type: 'ADD'; toast: ToastData }
  | { type: 'REMOVE'; id: string }

function reducer(state: ToastState, action: ToastAction): ToastState {
  switch (action.type) {
    case 'ADD':
      return { toasts: [...state.toasts, action.toast] }
    case 'REMOVE':
      return { toasts: state.toasts.filter((t) => t.id !== action.id) }
    default:
      return state
  }
}

const listeners: Array<(state: ToastState) => void> = []
let memoryState: ToastState = { toasts: [] }

function dispatch(action: ToastAction) {
  memoryState = reducer(memoryState, action)
  listeners.forEach((l) => l(memoryState))
}

let count = 0
function genId() {
  count = (count + 1) % Number.MAX_SAFE_INTEGER
  return count.toString()
}

export function toast({
  title,
  description,
  variant = 'default',
  duration = 4000,
}: Omit<ToastData, 'id'>) {
  const id = genId()
  dispatch({ type: 'ADD', toast: { id, title, description, variant, duration } })
  setTimeout(() => dispatch({ type: 'REMOVE', id }), duration)
  return id
}

export function useToast() {
  const [state, setState] = React.useState<ToastState>(memoryState)

  React.useEffect(() => {
    listeners.push(setState)
    return () => {
      const idx = listeners.indexOf(setState)
      if (idx > -1) listeners.splice(idx, 1)
    }
  }, [])

  return {
    toasts: state.toasts,
    toast,
    dismiss: (id: string) => dispatch({ type: 'REMOVE', id }),
  }
}
