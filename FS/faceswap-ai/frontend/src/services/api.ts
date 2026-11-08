import axios, { AxiosProgressEvent } from 'axios'
import type {
  Project,
  DetectionResult,
  ProcessingJob,
  UploadedVideo,
  UploadProgress,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Interceptor de errores ───────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const message =
      error.response?.data?.detail ?? error.message ?? 'Error desconocido'
    return Promise.reject(new Error(message))
  }
)

// ─── Proyectos ────────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () =>
    apiClient.get<Project[]>('/projects').then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Project>(`/projects/${id}`).then((r) => r.data),

  create: (name: string) =>
    apiClient.post<Project>('/projects', { name }).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/projects/${id}`).then((r) => r.data),
}

// ─── Videos ───────────────────────────────────────────────────────────────────

export const videosApi = {
  upload: (
    projectId: string,
    file: File,
    onProgress?: (p: UploadProgress) => void
  ): Promise<UploadedVideo> => {
    const form = new FormData()
    form.append('file', file)
    return apiClient
      .post<UploadedVideo>(`/projects/${projectId}/video`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e: AxiosProgressEvent) => {
          if (onProgress && e.total) {
            onProgress({
              loaded: e.loaded,
              total: e.total,
              percentage: Math.round((e.loaded / e.total) * 100),
            })
          }
        },
      })
      .then((r) => r.data)
  },

  remove: (projectId: string) =>
    apiClient.delete(`/projects/${projectId}/video`).then((r) => r.data),
}

// ─── Detección de rostros ─────────────────────────────────────────────────────

export const detectionApi = {
  start: (projectId: string) =>
    apiClient
      .post<{ jobId: string }>(`/projects/${projectId}/detect`)
      .then((r) => r.data),

  getResult: (projectId: string) =>
    apiClient
      .get<DetectionResult>(`/projects/${projectId}/detection`)
      .then((r) => r.data),
}

// ─── Fotos de reemplazo ───────────────────────────────────────────────────────

export const photosApi = {
  upload: (projectId: string, personId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    form.append('person_id', personId)
    return apiClient
      .post<{ photoId: string; url: string; validated: boolean }>(
        `/projects/${projectId}/photos`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      .then((r) => r.data)
  },

  remove: (projectId: string, personId: string) =>
    apiClient
      .delete(`/projects/${projectId}/photos/${personId}`)
      .then((r) => r.data),
}

// ─── Procesamiento ────────────────────────────────────────────────────────────

export const processingApi = {
  start: (projectId: string, assignments: Record<string, string>) =>
    apiClient
      .post<{ jobId: string }>(`/projects/${projectId}/process`, {
        assignments,
      })
      .then((r) => r.data),

  getJob: (jobId: string) =>
    apiClient.get<ProcessingJob>(`/jobs/${jobId}`).then((r) => r.data),

  getProjectJob: (projectId: string) =>
    apiClient
      .get<ProcessingJob>(`/projects/${projectId}/job`)
      .then((r) => r.data),
}

// ─── Settings de velocidad ───────────────────────────────────────────────────

export interface SpeedConfig {
  swap_frame_step: number
  apply_enhancement: boolean
  face_det_size: number
}
export const settingsApi = {
  getSpeed: () =>
    apiClient.get<SpeedConfig>('/settings/speed').then((r) => r.data),

  updateSpeed: (config: Partial<SpeedConfig>) =>
    apiClient.patch<SpeedConfig>('/settings/speed', config).then((r) => r.data),
}

export const outputApi = {
  getDownloadUrl: (projectId: string) =>
    `${BASE_URL}/api/v1/projects/${projectId}/output`,
}
