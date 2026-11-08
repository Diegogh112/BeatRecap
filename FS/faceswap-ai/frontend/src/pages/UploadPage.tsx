import { useCallback, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  Video,
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  Film,
  Gauge,
  HardDrive,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Progress } from '@/components/ui/Progress'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { videosApi, detectionApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { formatDuration, formatBytes } from '@/utils/format'
import { toast } from '@/hooks/useToast'
import type { UploadProgress, UploadedVideo } from '@/types'
import { cn } from '@/utils/cn'

const ACCEPTED_TYPES = {
  'video/mp4': ['.mp4'],
  'video/quicktime': ['.mov'],
  'video/x-msvideo': ['.avi'],
}
const MAX_DURATION_SECONDS = 300  // 5 min
const MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  // 2 GB

interface ValidationError {
  field: string
  message: string
}

export function UploadPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const {
    activeProject,
    updateProject,
    setUploadProgress,
    setIsUploading,
    uploadProgress,
    isUploading,
  } = useProjectStore()

  const [localFile, setLocalFile] = useState<File | null>(null)
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null)
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([])
  const [uploadedVideo, setUploadedVideo] = useState<UploadedVideo | null>(
    activeProject?.video ?? null
  )
  // Sync if activeProject already has video

  const videoRef = useRef<HTMLVideoElement>(null)

  // ─── Validación local (antes del upload) ──────────────────────────────────
  const validateFile = (file: File): ValidationError[] => {
    const errors: ValidationError[] = []
    const accepted = ['video/mp4', 'video/quicktime', 'video/x-msvideo']
    if (!accepted.includes(file.type)) {
      errors.push({ field: 'format', message: 'Formato no admitido. Usa MP4, MOV o AVI.' })
    }
    if (file.size > MAX_SIZE_BYTES) {
      errors.push({ field: 'size', message: `El archivo excede el tamaño máximo (${formatBytes(MAX_SIZE_BYTES)}).` })
    }
    return errors
  }

  const validateDuration = (duration: number): ValidationError[] => {
    if (duration > MAX_DURATION_SECONDS) {
      return [{ field: 'duration', message: `El video supera los 5 minutos (${formatDuration(duration)}).` }]
    }
    return []
  }

  // ─── Upload mutation ───────────────────────────────────────────────────────
  const uploadMutation = useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress: (p: UploadProgress) => void }) =>
      videosApi.upload(projectId!, file, onProgress),
    onSuccess: (video) => {
      setUploadedVideo(video)
      setIsUploading(false)
      setUploadProgress(null)
      if (activeProject) {
        const updated = { ...activeProject, video, status: 'video_uploaded' as const }
        updateProject(updated)
      }
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      toast({ title: 'Video cargado correctamente', variant: 'success' })
    },    onError: (err: Error) => {
      setIsUploading(false)
      setUploadProgress(null)
      toast({ title: 'Error al cargar', description: err.message, variant: 'destructive' })
    },
  })

  // ─── Start detection ───────────────────────────────────────────────────────
  const detectMutation = useMutation({
    mutationFn: () => detectionApi.start(projectId!),
    onSuccess: () => {
      if (activeProject) {
        updateProject({ ...activeProject, status: 'detecting' })
      }
      navigate(`/project/${projectId}/detect`)
    },
    onError: (err: Error) =>
      toast({ title: 'Error al iniciar detección', description: err.message, variant: 'destructive' }),
  })

  // ─── Dropzone ──────────────────────────────────────────────────────────────
  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0]
      if (!file) return

      const errors = validateFile(file)
      if (errors.length) {
        setValidationErrors(errors)
        return
      }
      setValidationErrors([])

      // Preview local antes de subir
      const url = URL.createObjectURL(file)
      setLocalFile(file)
      setLocalPreviewUrl(url)
    },
    []
  )

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    disabled: isUploading,
  })

  const handleVideoDurationLoad = () => {
    const video = videoRef.current
    if (!video) return
    const errors = validateDuration(video.duration)
    if (errors.length) {
      setValidationErrors(errors)
      setLocalFile(null)
      if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl)
      setLocalPreviewUrl(null)
    }
  }

  const handleUpload = () => {
    if (!localFile || !projectId) return
    setIsUploading(true)
    uploadMutation.mutate({
      file: localFile,
      onProgress: (p) => setUploadProgress(p),
    })
  }

  const handleRemove = () => {
    if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl)
    setLocalFile(null)
    setLocalPreviewUrl(null)
    setValidationErrors([])
    setUploadedVideo(null)
  }

  const hasVideo = !!uploadedVideo
  const readyToDetect = hasVideo && activeProject?.status !== 'detecting'

  return (
    <div className="space-y-6 animate-fade-in max-w-3xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-bold">1</span>
          Cargar video
          <span className="text-border">›</span>
          <span>Detectar rostros</span>
          <span className="text-border">›</span>
          <span>Asignar reemplazos</span>
          <span className="text-border">›</span>
          <span>Procesar</span>
        </div>
        <h1 className="text-2xl font-bold">Cargar video</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sube el video que deseas procesar. Máximo 5 minutos. Formatos: MP4, MOV, AVI.
        </p>
      </div>

      {/* Zona de drop — solo si no hay video cargado */}
      {!hasVideo && !localFile && (
        <div
          {...getRootProps()}
          className={cn(
            'relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 text-center transition-all cursor-pointer',
            isDragActive && !isDragReject
              ? 'border-primary bg-primary/5'
              : isDragReject
              ? 'border-destructive bg-destructive/5'
              : 'border-border hover:border-primary/50 hover:bg-accent/30'
          )}
        >
          <input {...getInputProps()} />
          <div className={cn(
            'flex h-16 w-16 items-center justify-center rounded-2xl transition-colors',
            isDragActive ? 'bg-primary/20' : 'bg-muted'
          )}>
            {isDragActive
              ? <Video className="h-8 w-8 text-primary" />
              : <Upload className="h-8 w-8 text-muted-foreground" />
            }
          </div>
          <div>
            <p className="font-semibold text-base">
              {isDragActive ? 'Suelta el archivo aquí' : 'Arrastra tu video aquí'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              o haz clic para seleccionarlo
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <Badge variant="outline">MP4</Badge>
            <Badge variant="outline">MOV</Badge>
            <Badge variant="outline">AVI</Badge>
            <span>·</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" /> Máx. 5 min
            </span>
          </div>
        </div>
      )}

      {/* Errores de validación */}
      {validationErrors.length > 0 && (
        <div className="flex flex-col gap-2">
          {validationErrors.map((e) => (
            <div
              key={e.field}
              className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
              {e.message}
            </div>
          ))}
        </div>
      )}

      {/* Preview local (antes del upload) */}
      {localFile && !hasVideo && (
        <div className="space-y-4">
          <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
            <video
              ref={videoRef}
              src={localPreviewUrl!}
              controls
              className="w-full h-full object-contain"
              onLoadedMetadata={handleVideoDurationLoad}
            />
          </div>

          {/* Info del archivo local */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: <Film className="h-4 w-4" />, label: 'Archivo', value: localFile.name },
              { icon: <HardDrive className="h-4 w-4" />, label: 'Tamaño', value: formatBytes(localFile.size) },
              { icon: <Video className="h-4 w-4" />, label: 'Formato', value: localFile.type.split('/')[1].toUpperCase() },
            ].map((info) => (
              <Card key={info.label} className="glass">
                <CardContent className="p-3 flex items-center gap-2">
                  <span className="text-muted-foreground">{info.icon}</span>
                  <div className="min-w-0">
                    <p className="text-[10px] text-muted-foreground">{info.label}</p>
                    <p className="text-xs font-medium truncate">{info.value}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Progress de upload */}
          {isUploading && uploadProgress && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Subiendo video...</span>
                <span>{uploadProgress.percentage}%</span>
              </div>
              <Progress value={uploadProgress.percentage} indicatorClassName="bg-gradient-to-r from-indigo-500 to-purple-600" />
              <p className="text-xs text-muted-foreground">
                {formatBytes(uploadProgress.loaded)} / {formatBytes(uploadProgress.total)}
              </p>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="gradient"
              loading={isUploading}
              onClick={handleUpload}
              disabled={validationErrors.length > 0}
            >
              <Upload className="h-4 w-4" />
              {isUploading ? 'Subiendo...' : 'Subir video'}
            </Button>
            <Button variant="outline" onClick={handleRemove} disabled={isUploading}>
              <X className="h-4 w-4" /> Cancelar
            </Button>
          </div>
        </div>
      )}

      {/* Video ya cargado al servidor */}
      {hasVideo && uploadedVideo && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
            Video cargado correctamente
          </div>

          <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
            <video
              src={uploadedVideo.url}
              controls
              className="w-full h-full object-contain"
            />
          </div>

          {/* Info del video */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: <Clock className="h-4 w-4" />, label: 'Duración', value: formatDuration(uploadedVideo.info.duration) },
              { icon: <Video className="h-4 w-4" />, label: 'Resolución', value: `${uploadedVideo.info.width}×${uploadedVideo.info.height}` },
              { icon: <Gauge className="h-4 w-4" />, label: 'FPS', value: `${uploadedVideo.info.fps} fps` },
              { icon: <HardDrive className="h-4 w-4" />, label: 'Tamaño', value: formatBytes(uploadedVideo.info.size) },            ].map((info) => (
              <Card key={info.label} className="glass">
                <CardContent className="p-3 flex items-center gap-2">
                  <span className="text-muted-foreground">{info.icon}</span>
                  <div>
                    <p className="text-[10px] text-muted-foreground">{info.label}</p>
                    <p className="text-sm font-semibold">{info.value}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex gap-3">
            <Button
              variant="gradient"
              loading={detectMutation.isPending}
              onClick={() => detectMutation.mutate()}
              disabled={!readyToDetect}
            >
              Detectar rostros
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={handleRemove}>
              <RefreshCw className="h-4 w-4" /> Cambiar video
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
