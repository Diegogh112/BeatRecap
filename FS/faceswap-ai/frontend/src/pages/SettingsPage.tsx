import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield,
  Cpu,
  HardDrive,
  Info,
  ExternalLink,
  Gauge,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { settingsApi } from '@/services/api'
import { toast } from '@/hooks/useToast'
import { cn } from '@/utils/cn'

// ─── Presets de velocidad ─────────────────────────────────────────────────────

interface SpeedPreset {
  id: string
  label: string
  description: string
  badge: string
  badgeVariant: 'success' | 'warning' | 'info' | 'destructive' | 'purple'
  swap_frame_step: number
  apply_enhancement: boolean
  face_det_size: number
  estimatedTime: string   // para video de 30s
  quality: number         // 0–100 para la barra visual
  speed: number           // 0–100 para la barra visual
}

const PRESETS: SpeedPreset[] = [
  {
    id: 'ultra_fast',
    label: 'Ultra rápido',
    description: 'Procesa 1 de cada 10 frames. Sin mejora de calidad. Detector pequeño.',
    badge: '~5 min',
    badgeVariant: 'success',
    swap_frame_step: 10,
    apply_enhancement: false,
    face_det_size: 320,
    estimatedTime: '~5 min (video 30s)',
    quality: 30,
    speed: 95,
  },
  {
    id: 'fast',
    label: 'Rápido',
    description: 'Procesa 1 de cada 5 frames. Sin mejora de calidad. Detector mediano.',
    badge: '~10 min',
    badgeVariant: 'info',
    swap_frame_step: 5,
    apply_enhancement: false,
    face_det_size: 320,
    estimatedTime: '~10 min (video 30s)',
    quality: 50,
    speed: 75,
  },
  {
    id: 'balanced',
    label: 'Equilibrado',
    description: 'Procesa 1 de cada 3 frames. Sin mejora de calidad. Detector preciso.',
    badge: '~15 min',
    badgeVariant: 'warning',
    swap_frame_step: 3,
    apply_enhancement: false,
    face_det_size: 640,
    estimatedTime: '~15 min (video 30s)',
    quality: 70,
    speed: 50,
  },
  {
    id: 'quality',
    label: 'Alta calidad',
    description: 'Todos los frames con GFPGAN activado. Máxima nitidez facial.',
    badge: '~45 min',
    badgeVariant: 'destructive',
    swap_frame_step: 1,
    apply_enhancement: true,
    face_det_size: 640,
    estimatedTime: '~45 min (video 30s)',
    quality: 100,
    speed: 10,
  },
]

function SpeedBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="relative h-1.5 w-full rounded-full bg-secondary overflow-hidden">
      <div
        className={cn('h-full rounded-full transition-all duration-500', color)}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function SettingsPage() {
  const queryClient = useQueryClient()
  const [activePreset, setActivePreset] = useState<string | null>(null)

  const { data: speedConfig, isLoading: loadingConfig } = useQuery({
    queryKey: ['speed-config'],
    queryFn: settingsApi.getSpeed,
  })

  // Detectar preset activo cuando llegan los datos
  useEffect(() => {
    if (!speedConfig) return
    const match = PRESETS.find(
      (p) =>
        p.swap_frame_step === speedConfig.swap_frame_step &&
        p.apply_enhancement === speedConfig.apply_enhancement &&
        p.face_det_size === speedConfig.face_det_size
    )
    setActivePreset(match?.id ?? 'custom')
  }, [speedConfig])

  const updateMutation = useMutation({
    mutationFn: settingsApi.updateSpeed,
    onSuccess: (data) => {
      queryClient.setQueryData(['speed-config'], data)
      toast({ title: 'Configuración guardada', variant: 'success' })
    },
    onError: () =>
      toast({ title: 'Error al guardar', variant: 'destructive' }),
  })

  const applyPreset = (preset: SpeedPreset) => {
    setActivePreset(preset.id)
    updateMutation.mutate({
      swap_frame_step: preset.swap_frame_step,
      apply_enhancement: preset.apply_enhancement,
      face_det_size: preset.face_det_size,
    })
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Configuración</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ajusta el rendimiento y la privacidad de la aplicación
        </p>
      </div>

      {/* ── Velocidad de procesamiento ────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Velocidad de procesamiento</CardTitle>
          </div>
          <CardDescription>
            Elige entre velocidad y calidad. Los cambios aplican al siguiente video procesado.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">

          {/* Config actual */}
          {loadingConfig ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Cargando...
            </div>
          ) : speedConfig && (
            <div className="flex flex-wrap gap-2 p-3 rounded-lg bg-muted/50 text-xs">
              <span className="text-muted-foreground">Configuración actual:</span>
              <Badge variant="outline">
                Paso: 1 de cada {speedConfig.swap_frame_step} frames
              </Badge>
              <Badge variant={speedConfig.apply_enhancement ? 'success' : 'default'}>
                GFPGAN: {speedConfig.apply_enhancement ? 'activado' : 'desactivado'}
              </Badge>
              <Badge variant="outline">
                Detector: {speedConfig.face_det_size}px
              </Badge>
            </div>
          )}

          {/* Presets */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {PRESETS.map((preset) => {
              const isActive = activePreset === preset.id
              const isPending = updateMutation.isPending && activePreset === preset.id
              return (
                <button
                  key={preset.id}
                  onClick={() => applyPreset(preset)}
                  disabled={updateMutation.isPending}
                  className={cn(
                    'relative text-left rounded-xl border p-4 transition-all',
                    'hover:border-primary/50 hover:bg-accent/30',
                    isActive
                      ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                      : 'border-border bg-card',
                  )}
                >
                  {/* Check activo */}
                  {isActive && !isPending && (
                    <CheckCircle2 className="absolute top-3 right-3 h-4 w-4 text-primary" />
                  )}
                  {isPending && (
                    <Loader2 className="absolute top-3 right-3 h-4 w-4 text-primary animate-spin" />
                  )}

                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-semibold text-sm">{preset.label}</span>
                    <Badge variant={preset.badgeVariant} className="text-[10px] h-4">
                      {preset.badge}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed mb-3">
                    {preset.description}
                  </p>

                  {/* Barras de velocidad/calidad */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground w-14">Velocidad</span>
                      <SpeedBar value={preset.speed} color="bg-emerald-500" />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground w-14">Calidad</span>
                      <SpeedBar value={preset.quality} color="bg-indigo-500" />
                    </div>
                  </div>

                  <p className="mt-2 text-[10px] text-muted-foreground/60">
                    {preset.estimatedTime}
                  </p>
                </button>
              )
            })}
          </div>

          <p className="text-xs text-muted-foreground/60 leading-relaxed">
            Los tiempos son estimados para CPU sin GPU (AMD Radeon). Con GPU NVIDIA serían
            10–30x más rápidos. Los frames saltados copian automáticamente el resultado
            del frame anterior, por lo que el movimiento se ve fluido.
          </p>
        </CardContent>
      </Card>

      {/* ── Modelos de IA ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-indigo-400" />
            <CardTitle className="text-base">Motor de inteligencia artificial</CardTitle>
          </div>
          <CardDescription>Modelos y tecnologías utilizadas</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { name: 'InsightFace (buffalo_l)', role: 'Detección y embeddings faciales', status: 'Activo' },
            { name: 'SCRFD', role: 'Detección rápida de rostros', status: 'Activo' },
            { name: 'ArcFace', role: 'Agrupación de identidades', status: 'Activo' },
            { name: 'InSwapper 128', role: 'Motor de intercambio facial', status: 'Activo' },
            { name: 'GFPGAN', role: 'Mejora de calidad post-swap', status: 'Opcional' },
            { name: 'ByteTrack', role: 'Seguimiento entre fotogramas', status: 'Activo' },
            { name: 'FFmpeg', role: 'Procesamiento de video', status: 'Activo' },
          ].map((m) => (
            <div key={m.name} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{m.name}</p>
                <p className="text-xs text-muted-foreground">{m.role}</p>
              </div>
              <Badge variant={m.status === 'Activo' ? 'success' : m.status === 'Opcional' ? 'warning' : 'default'}>
                {m.status}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ── Privacidad ────────────────────────────────────────────────────── */}
      <Card className="border-amber-500/30 bg-amber-950/10">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-amber-400" />
            <CardTitle className="text-base">Uso responsable</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <ul className="list-disc pl-5 space-y-1.5">
            <li>Debes tener autorización para usar los videos e imágenes cargados.</li>
            <li>Prohibido su uso para suplantación de identidad, acoso o fraude.</li>
            <li>No generar contenido íntimo no consentido.</li>
            <li>Los resultados son contenido manipulado por IA (deepfake).</li>
          </ul>
        </CardContent>
      </Card>

      {/* ── Almacenamiento ────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <HardDrive className="h-5 w-5 text-purple-400" />
            <CardTitle className="text-base">Almacenamiento y privacidad</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Los archivos subidos se almacenan temporalmente durante 24 horas.</p>
          <p>Los videos y fotografías no se usan para entrenar modelos de IA.</p>
          <p>Los archivos se eliminan automáticamente por tareas programadas.</p>
        </CardContent>
      </Card>

      {/* ── Acerca de ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-sky-400" />
            <CardTitle className="text-base">Acerca de FaceSwap AI</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <div className="flex justify-between">
            <span>Versión</span><span className="font-mono">1.0.0</span>
          </div>
          <div className="flex justify-between">
            <span>Frontend</span><span className="font-mono">React 18 + TypeScript</span>
          </div>
          <div className="flex justify-between">
            <span>Backend</span><span className="font-mono">FastAPI + Celery</span>
          </div>
          <div className="flex items-center gap-2 pt-3 border-t border-border">
            <a href="https://github.com/deepinsight/insightface" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-primary hover:underline text-xs">
              InsightFace <ExternalLink className="h-3 w-3" />
            </a>
            <span className="text-muted-foreground/40">·</span>
            <a href="https://github.com/TencentARC/GFPGAN" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-primary hover:underline text-xs">
              GFPGAN <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
