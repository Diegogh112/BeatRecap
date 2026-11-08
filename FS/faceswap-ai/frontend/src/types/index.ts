// ─── Video ────────────────────────────────────────────────────────────────────

export interface VideoMetaInfo {
  duration: number        // segundos
  width: number
  height: number
  fps: number
  size: number            // bytes
  format: string
}

export interface UploadedVideo {
  id: string
  filename: string
  original_name: string
  url: string
  uploaded_at: string
  // Campos planos (también expuestos por la API para backward compat)
  duration: number
  width: number
  height: number
  fps: number
  size: number
  format: string
  // Objeto anidado que espera el frontend
  info: VideoMetaInfo
}

// ─── Rostros detectados ───────────────────────────────────────────────────────

export interface DetectedPerson {
  id: string
  person_id: string
  label: string
  thumbnail_url: string
  face_count: number
  first_frame: number
  last_frame: number
}

export interface DetectionResult {
  id: string
  project_id: string
  total_persons: number
  persons: DetectedPerson[]
  total_frames_analyzed: number
  processing_time_ms: number
  created_at: string
}

// ─── Asignaciones de reemplazo ────────────────────────────────────────────────

export interface FaceAssignment {
  id: string
  person_id: string
  photo_url: string | null
  photo_id: string | null
  validated: boolean
}

// ─── Proyecto ─────────────────────────────────────────────────────────────────

export type ProjectStatus =
  | 'created'
  | 'video_uploaded'
  | 'detecting'
  | 'detection_complete'
  | 'assigning'
  | 'queued'
  | 'processing'
  | 'completed'
  | 'error'

export interface Project {
  id: string
  name: string
  status: ProjectStatus
  video: UploadedVideo | null
  detection_result: DetectionResult | null
  assignments: FaceAssignment[]
  output_video_url: string | null
  output_video_size: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

// ─── Procesamiento / Cola ─────────────────────────────────────────────────────

export type ProcessingStage =
  | 'queued'
  | 'extracting_frames'
  | 'detecting_faces'
  | 'tracking_faces'
  | 'swapping_faces'
  | 'enhancing'
  | 'reconstructing_video'
  | 'finalizing'
  | 'completed'
  | 'error'

export interface ProcessingJob {
  id: string
  project_id: string
  status: ProcessingStage
  progress: number          // 0–100
  current_stage: string
  estimated_seconds: number | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  created_at: string
}

// ─── Upload progress ──────────────────────────────────────────────────────────

export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}
