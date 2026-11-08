/**
 * Hook para polling del estado de un ProcessingJob.
 *
 * - Hace polling cada `interval` ms mientras el job está activo.
 * - Detiene el polling al completarse (completed o error).
 * - Usa un ref para que el interval siempre llame a la última versión de poll
 *   (evita closures stale cuando activeProject cambia entre renders).
 */

import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { processingApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import type { ProcessingJob } from '@/types'

interface UseJobPollingOptions {
  projectId: string | undefined
  interval?: number
  enabled?: boolean
  onCompleted?: (job: ProcessingJob) => void
  onError?: (job: ProcessingJob) => void
  onProgress?: (job: ProcessingJob) => void
}

interface UseJobPollingResult {
  job: ProcessingJob | null
  isPolling: boolean
  startPolling: () => void
  stopPolling: () => void
}

const TERMINAL_STATES = new Set(['completed', 'error'])
const DEFAULT_INTERVAL = 2000

export function useJobPolling({
  projectId,
  interval = DEFAULT_INTERVAL,
  enabled = true,
  onCompleted,
  onError,
  onProgress,
}: UseJobPollingOptions): UseJobPollingResult {
  const { activeJob, setActiveJob } = useProjectStore()
  const queryClient = useQueryClient()
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isPollingRef = useRef(false)

  // Refs para callbacks — siempre tienen el valor más reciente
  const onCompletedRef = useRef(onCompleted)
  const onErrorRef = useRef(onError)
  const onProgressRef = useRef(onProgress)
  onCompletedRef.current = onCompleted
  onErrorRef.current = onError
  onProgressRef.current = onProgress

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    isPollingRef.current = false
  }, [])

  // Poll function — no tiene dependencias externas que cambian entre renders
  const poll = useCallback(async () => {
    if (!projectId) return
    try {
      const job = await processingApi.getProjectJob(projectId)
      setActiveJob(job)
      onProgressRef.current?.(job)

      if (TERMINAL_STATES.has(job.status)) {
        stopPolling()
        queryClient.invalidateQueries({ queryKey: ['projects'] })
        queryClient.invalidateQueries({ queryKey: ['project', projectId] })
        if (job.status === 'completed') {
          onCompletedRef.current?.(job)
        } else {
          onErrorRef.current?.(job)
        }
      }
    } catch {
      // Job puede no existir aún — seguir esperando
    }
  }, [projectId, stopPolling, setActiveJob, queryClient])

  const startPolling = useCallback(() => {
    if (isPollingRef.current) return
    isPollingRef.current = true
    poll()
    pollingRef.current = setInterval(poll, interval)
  }, [poll, interval])

  useEffect(() => {
    if (!enabled || !projectId) return
    // Limpiar job anterior al montar (evita mostrar "completed" de proyecto previo)
    if (activeJob && activeJob.project_id !== projectId) {
      setActiveJob(null)
    }
    if (activeJob && activeJob.project_id === projectId && TERMINAL_STATES.has(activeJob.status)) return
    startPolling()
    return stopPolling
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, enabled])

  return {
    job: activeJob,
    isPolling: isPollingRef.current,
    startPolling,
    stopPolling,
  }
}
