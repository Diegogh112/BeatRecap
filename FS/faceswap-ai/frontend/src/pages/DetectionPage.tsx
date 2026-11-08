import { useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Loader2,
  Users,
  ArrowRight,
  RefreshCw,
  User,
  Film,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { Progress } from '@/components/ui/Progress'
import { detectionApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { toast } from '@/hooks/useToast'
import type { DetectedPerson } from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export function DetectionPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const {
    activeProject,
    updateProject,
    setDetectionResult,
    isDetecting,
    setIsDetecting,
    detectionProgress,
    setDetectionProgress,
  } = useProjectStore()

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll para el resultado de detección
  const { data: detectionResult } = useQuery({
    queryKey: ['detection', projectId],
    queryFn: () => detectionApi.getResult(projectId!),
    enabled: false,
  })

  // Poll de estado mientras detecta
  useEffect(() => {
    const project = activeProject
    if (!project || !projectId) return

    if (project.status === 'detecting') {
      setIsDetecting(true)
      // Simular progreso mientras se espera al backend
      let simProgress = 0
      pollingRef.current = setInterval(async () => {
        simProgress = Math.min(simProgress + Math.random() * 8, 90)
        setDetectionProgress(Math.round(simProgress))
        try {
          const result = await detectionApi.getResult(projectId)
          if (result) {
            clearInterval(pollingRef.current!)
            setDetectionProgress(100)
            setDetectionResult(result)
            setIsDetecting(false)
            updateProject({ ...project, status: 'detection_complete', detection_result: result })
          }
        } catch {
          // Aún procesando
        }
      }, 2000)
    } else if (project.status === 'detection_complete' && project.detection_result) {
      setDetectionResult(project.detection_result)
      setDetectionProgress(100)
      setIsDetecting(false)
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [activeProject?.status, projectId])

  const result = activeProject?.detection_result ?? detectionResult
  const detecting = isDetecting || activeProject?.status === 'detecting'

  return (
    <div className="space-y-6 animate-fade-in max-w-3xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-bold">1</span>
        <span className="line-through opacity-50">Cargar video</span>
        <span className="text-border">›</span>
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-bold">2</span>
        Detectar rostros
        <span className="text-border">›</span>
        <span>Asignar reemplazos</span>
        <span className="text-border">›</span>
        <span>Procesar</span>
      </div>

      <div>
        <h1 className="text-2xl font-bold">Detección de rostros</h1>
        <p className="text-sm text-muted-foreground mt-1">
          La IA analiza el video, detecta todas las personas y agrupa las identidades.
        </p>
      </div>

      {/* Estado: detectando */}
      {detecting && (
        <Card className="glass">
          <CardContent className="py-8 flex flex-col items-center gap-6 text-center">
            <div className="relative">
              <div className="h-20 w-20 rounded-full border-4 border-muted flex items-center justify-center">
                <Users className="h-8 w-8 text-primary animate-pulse" />
              </div>
              <Loader2 className="absolute -top-1 -right-1 h-6 w-6 text-primary animate-spin" />
            </div>
            <div>
              <p className="font-semibold text-lg">Analizando video...</p>
              <p className="text-sm text-muted-foreground mt-1">
                Detectando y agrupando identidades en todos los fotogramas
              </p>
            </div>
            <div className="w-full max-w-sm space-y-2">
              <Progress
                value={detectionProgress}
                indicatorClassName="bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500"
              />
              <p className="text-xs text-muted-foreground">{detectionProgress}% completado</p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center text-xs text-muted-foreground">
              {['Extrayendo fotogramas', 'Detectando rostros', 'Agrupando identidades', 'Calculando embeddings'].map(
                (step, i) => (
                  <span
                    key={step}
                    className={`flex items-center gap-1 px-2 py-1 rounded-full border ${
                      detectionProgress > i * 25
                        ? 'border-primary/30 text-primary bg-primary/5'
                        : 'border-border'
                    }`}
                  >
                    {detectionProgress > i * 25 ? '✓' : '○'} {step}
                  </span>
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resultado de detección */}
      {!detecting && result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <span className="font-semibold">
                {result.total_persons} persona{result.total_persons !== 1 ? 's' : ''} detectada
                {result.total_persons !== 1 ? 's' : ''}
              </span>
              <Badge variant="success">Detección completa</Badge>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (projectId) {
                  setIsDetecting(true)
                  detectionApi.start(projectId).catch(() =>
                    toast({ title: 'Error al reiniciar detección', variant: 'destructive' })
                  )
                }
              }}
            >
              <RefreshCw className="h-4 w-4" /> Volver a detectar
            </Button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {result.persons.map((person: DetectedPerson) => (
              <Card key={person.person_id} className="glass overflow-hidden">
                <div className="aspect-square bg-muted relative">
                  {person.thumbnail_url ? (
                    <img
                      src={`${BASE_URL}${person.thumbnail_url}`}
                      alt={person.label}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <User className="h-12 w-12 text-muted-foreground/30" />
                    </div>
                  )}
                </div>
                <CardContent className="p-3">
                  <p className="font-semibold text-sm">{person.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                    <Film className="h-3 w-3" />
                    {person.face_count} aparición{person.face_count !== 1 ? 'es' : ''}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              variant="gradient"
              onClick={() => navigate(`/project/${projectId}/assign`)}
            >
              Asignar reemplazos
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={() => navigate(`/project/${projectId}/upload`)}>
              Cambiar video
            </Button>
          </div>
        </div>
      )}

      {/* Sin datos */}
      {!detecting && !result && (
        <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-border rounded-xl">
          <Users className="h-10 w-10 text-muted-foreground/30 mb-3" />
          <p className="text-muted-foreground">Sin resultados de detección</p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => navigate(`/project/${projectId}/upload`)}
          >
            Volver a cargar video
          </Button>
        </div>
      )}
    </div>
  )
}
