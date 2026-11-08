import { useNavigate, useParams } from 'react-router-dom'
import {
  Loader2,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Clock,
  Film,
  Zap,
  Search,
  Layers,
  Sparkles,
  Clapperboard,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { Progress } from '@/components/ui/Progress'
import { useJobPolling } from '@/hooks/useJobPolling'
import { toast } from '@/hooks/useToast'
import type { ProcessingJob, ProcessingStage } from '@/types'
import { cn } from '@/utils/cn'

// ─── Configuración de etapas ──────────────────────────────────────────────────

const stageConfig: Record<
  ProcessingStage,
  { label: string; icon: React.ReactNode; description: string; color: string }
> = {
  queued: {
    label: 'En cola',
    icon: <Clock className="h-4 w-4" />,
    description: 'El trabajo está esperando disponibilidad del procesador...',
    color: 'text-amber-400',
  },
  extracting_frames: {
    label: 'Extrayendo fotogramas',
    icon: <Film className="h-4 w-4" />,
    description: 'Descomponiendo el video en imágenes individuales con FFmpeg...',
    color: 'text-sky-400',
  },
  detecting_faces: {
    label: 'Detectando rostros',
    icon: <Search className="h-4 w-4" />,
    description: 'InsightFace analiza cada fotograma y localiza los rostros...',
    color: 'text-indigo-400',
  },
  tracking_faces: {
    label: 'Inicializando tracker',
    icon: <Cpu className="h-4 w-4" />,
    description: 'Cargando fotografías de reemplazo y embeddings de referencia...',
    color: 'text-purple-400',
  },
  swapping_faces: {
    label: 'Intercambiando rostros',
    icon: <Zap className="h-4 w-4" />,
    description: 'InSwapper + ByteTrack sustituyen los rostros frame a frame...',
    color: 'text-primary',
  },
  enhancing: {
    label: 'Mejorando calidad',
    icon: <Sparkles className="h-4 w-4" />,
    description: 'GFPGAN restaura nitidez y detalle facial en cada fotograma...',
    color: 'text-pink-400',
  },
  reconstructing_video: {
    label: 'Reconstruyendo video',
    icon: <Layers className="h-4 w-4" />,
    description: 'FFmpeg ensambla los fotogramas y restaura el audio original...',
    color: 'text-teal-400',
  },
  finalizing: {
    label: 'Finalizando',
    icon: <Clapperboard className="h-4 w-4" />,
    description: 'Aplicando últimos ajustes y guardando el archivo final...',
    color: 'text-emerald-400',
  },
  completed: {
    label: 'Completado',
    icon: <CheckCircle2 className="h-4 w-4" />,
    description: 'El video fue generado exitosamente.',
    color: 'text-emerald-400',
  },
  error: {
    label: 'Error',
    icon: <AlertCircle className="h-4 w-4" />,
    description: 'Ocurrió un error durante el procesamiento.',
    color: 'text-destructive',
  },
}

// Orden visual de etapas (sin error/completed)
const stageOrder: ProcessingStage[] = [
  'queued',
  'extracting_frames',
  'detecting_faces',
  'tracking_faces',
  'swapping_faces',
  'enhancing',
  'reconstructing_video',
  'finalizing',
]

// ─── Componente de etapa ──────────────────────────────────────────────────────

function StageStep({
  stage,
  currentIndex,
  index,
}: {
  stage: ProcessingStage
  currentIndex: number
  index: number
}) {
  const cfg = stageConfig[stage]
  const done = index < currentIndex
  const active = index === currentIndex

  return (
    <div className={cn(
      'flex flex-col items-center gap-1.5 p-2 rounded-xl text-center transition-all',
      done && 'text-emerald-400',
      active && 'text-primary bg-primary/5 ring-1 ring-primary/20',
      !done && !active && 'text-muted-foreground/30',
    )}>
      <div className="text-base">
        {done ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        ) : (
          <span className={active ? 'text-primary' : ''}>{cfg.icon}</span>
        )}
      </div>
      <span className="text-[9px] leading-tight font-medium">{cfg.label}</span>
    </div>
  )
}

// ─── ETA formatter ────────────────────────────────────────────────────────────

function formatEta(seconds: number | null | undefined): string | null {
  if (!seconds || seconds <= 0) return null
  if (seconds < 60) return `~${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return s > 0 ? `~${m}m ${s}s` : `~${m} min`
}

// ─── Página principal ─────────────────────────────────────────────────────────

export function ProcessingPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const { job } = useJobPolling({
    projectId,
    interval: 2500,
    enabled: true,
    onCompleted: (_j: ProcessingJob) => {
      toast({ title: '¡Video generado!', description: 'Tu video está listo para descargar.', variant: 'success' })
      navigate(`/project/${projectId}/result`)
    },
    onError: (j: ProcessingJob) => {
      toast({
        title: 'Error en el procesamiento',
        description: j.error_message ?? 'Error desconocido',
        variant: 'destructive',
      })
    },
  })

  const currentStage: ProcessingStage = (job?.status as ProcessingStage) ?? 'queued'
  const progress = job?.progress ?? 0
  const stageCfg = stageConfig[currentStage]
  const currentIndex = stageOrder.indexOf(currentStage)
  const isTerminal = currentStage === 'completed' || currentStage === 'error'
  const isActive = !isTerminal

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {['Cargar', 'Detectar', 'Asignar', 'Procesar'].map((step, i) => (
          <span key={step} className="flex items-center gap-1">
            {i > 0 && <span className="text-border">›</span>}
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold',
              i === 3 ? 'bg-primary text-primary-foreground' : 'bg-muted',
            )}>
              {i + 1}
            </span>
            <span className={i < 3 ? 'line-through opacity-40' : ''}>
              {step}
            </span>
          </span>
        ))}
      </div>

      <div>
        <h1 className="text-2xl font-bold">
          {currentStage === 'completed' ? 'Video listo' :
           currentStage === 'error' ? 'Error en procesamiento' :
           'Procesando video'}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {currentStage === 'completed'
            ? 'El intercambio de rostros se completó exitosamente.'
            : currentStage === 'error'
            ? 'El procesamiento falló. Puedes reintentar desde la configuración.'
            : 'El motor de IA está trabajando en tu video. No cierres esta página.'}
        </p>
      </div>

      {/* Tarjeta principal */}
      <Card className="glass">
        <CardContent className="py-8 space-y-7">

          {/* Estado central */}
          <div className="flex flex-col items-center text-center gap-4">
            <div className={cn(
              'relative flex h-24 w-24 items-center justify-center rounded-full border-4',
              currentStage === 'completed'
                ? 'border-emerald-500 bg-emerald-950/30'
                : currentStage === 'error'
                ? 'border-destructive bg-destructive/10'
                : 'border-primary/30 bg-primary/5',
            )}>
              <span className={cn('scale-[1.8]', stageCfg.color)}>
                {stageCfg.icon}
              </span>
              {isActive && (
                <Loader2 className="absolute -top-1 -right-1 h-6 w-6 text-primary animate-spin" />
              )}
            </div>

            <div>
              <div className="flex items-center justify-center gap-2 mb-1.5">
                <Badge variant={
                  currentStage === 'completed' ? 'success' :
                  currentStage === 'error' ? 'destructive' :
                  'warning'
                }>
                  {stageCfg.label}
                </Badge>
                {isActive && (
                  <span className="text-xs text-muted-foreground animate-pulse">
                    en progreso
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground max-w-xs">
                {stageCfg.description}
              </p>
              {job?.estimated_seconds && isActive && (
                <p className="text-xs text-muted-foreground/70 mt-1.5">
                  Tiempo estimado: {formatEta(job.estimated_seconds)}
                </p>
              )}
            </div>
          </div>

          {/* Barra de progreso */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Progreso total</span>
              <span className="font-mono tabular-nums">{progress}%</span>
            </div>
            <Progress
              value={progress}
              className="h-3"
              indicatorClassName={cn(
                'transition-all duration-700',
                currentStage === 'completed'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  : currentStage === 'error'
                  ? 'bg-destructive'
                  : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500',
              )}
            />
          </div>

          {/* Pasos de pipeline */}
          <div className="grid grid-cols-4 gap-2">
            {stageOrder.map((stage, i) => (
              <StageStep
                key={stage}
                stage={stage}

                currentIndex={currentIndex}
                index={i}
              />
            ))}
          </div>

        </CardContent>
      </Card>

      {/* Panel de error */}
      {currentStage === 'error' && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-4 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm">Error en el procesamiento</p>
              <p className="text-sm text-muted-foreground mt-1 break-words">
                {job?.error_message ?? 'Error desconocido. Revisa los logs del servidor.'}
              </p>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate(`/project/${projectId}/assign`)}
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Reintentar
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigate('/')}
                >
                  Ir al inicio
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Éxito — redirige automáticamente */}
      {currentStage === 'completed' && (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <CheckCircle2 className="h-12 w-12 text-emerald-400" />
          <p className="font-semibold text-lg">¡Video generado exitosamente!</p>
          <p className="text-sm text-muted-foreground">Redirigiendo a la pantalla de resultados...</p>
        </div>
      )}

      {/* Aviso informativo */}
      {isActive && (
        <div className="flex items-start gap-2 rounded-lg border border-border p-3 text-xs text-muted-foreground">
          <Cpu className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground/60" />
          <p>
            El tiempo depende de la duración del video y el hardware disponible.
            Videos de 5 minutos pueden tardar entre 5 minutos (GPU RTX 4090) y
            90 minutos (CPU de 8 núcleos).
          </p>
        </div>
      )}
    </div>
  )
}
