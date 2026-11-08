import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Download,
  PlusCircle,
  CheckCircle2,
  Clock,
  HardDrive,
  Video,
  SplitSquareHorizontal,
  Users,
  Film,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CompareSlider } from '@/components/video/CompareSlider'
import { outputApi, projectsApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { formatDuration, formatBytes } from '@/utils/format'
import { cn } from '@/utils/cn'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

type ViewMode = 'result' | 'compare'

export function ResultPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { setActiveProject } = useProjectStore()
  const [viewMode, setViewMode] = useState<ViewMode>('result')

  // Siempre carga desde la API — no usar initialData del store para evitar datos stale
  const { data: project, isLoading, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
    staleTime: 0,           // siempre refrescar al entrar
    refetchOnMount: true,
  })

  const outputUrl = `${BASE_URL}${outputApi.getDownloadUrl(projectId!)}`
  const originalUrl = project?.video
    ? `${BASE_URL}/api/v1/projects/${projectId}/video/stream`
    : null

  const hasOriginal = !!originalUrl

  const handleNewProject = () => {
    setActiveProject(null)
    navigate('/project/new')
  }

  // ── Loading ───────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-sm">Cargando resultado...</p>
        </div>
      </div>
    )
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (error || !project) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
        <p className="text-muted-foreground">No se pudo cargar el proyecto.</p>
        <Button variant="outline" onClick={() => navigate('/projects')}>
          Ver mis proyectos
        </Button>
      </div>
    )
  }

  const stats = [
    {
      icon: <Clock className="h-4 w-4" />,
      label: 'Duración',
      value: project.video ? formatDuration(project.video.duration) : '—',
    },
    {
      icon: <Video className="h-4 w-4" />,
      label: 'Resolución',
      value: project.video
        ? `${project.video.width}×${project.video.height}`
        : '—',
    },
    {
      icon: <Film className="h-4 w-4" />,
      label: 'FPS',
      value: project.video ? `${project.video.fps} fps` : '—',
    },
    {
      icon: <HardDrive className="h-4 w-4" />,
      label: 'Tamaño resultado',
      value: project.output_video_size
        ? formatBytes(project.output_video_size)
        : '—',
    },
    {
      icon: <Users className="h-4 w-4" />,
      label: 'Personas',
      value: project.detection_result
        ? `${project.detection_result.total_persons} detectada${project.detection_result.total_persons !== 1 ? 's' : ''}`
        : '—',
    },
    {
      icon: <CheckCircle2 className="h-4 w-4" />,
      label: 'Reemplazos',
      value: project.assignments
        ? `${project.assignments.filter((a) => a.validated).length} aplicado${project.assignments.filter((a) => a.validated).length !== 1 ? 's' : ''}`
        : '—',
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">

      {/* Cabecera */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/20 shrink-0">
            <CheckCircle2 className="h-6 w-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <p className="text-sm text-muted-foreground">
              El intercambio de rostros se completó exitosamente.
            </p>
          </div>
        </div>
        <Badge variant="success" className="shrink-0 mt-1">Completado</Badge>
      </div>

      {/* Selector de vista */}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={viewMode === 'result' ? 'default' : 'outline'}
          onClick={() => setViewMode('result')}
        >
          <Video className="h-4 w-4" /> Resultado
        </Button>
        {hasOriginal && (
          <Button
            size="sm"
            variant={viewMode === 'compare' ? 'default' : 'outline'}
            onClick={() => setViewMode('compare')}
          >
            <SplitSquareHorizontal className="h-4 w-4" /> Comparar
          </Button>
        )}
      </div>

      {/* Reproductor / Comparador */}
      {viewMode === 'result' ? (
        <div className="rounded-xl overflow-hidden bg-black aspect-video">
          <video
            key={outputUrl}          // key fuerza re-mount si cambia la URL
            src={outputUrl}
            controls
            playsInline
            preload="metadata"
            className="w-full h-full object-contain"
          />
        </div>
      ) : (
        hasOriginal && (
          <CompareSlider
            originalSrc={originalUrl!}
            resultSrc={outputUrl}
            className="aspect-video"
          />
        )
      )}

      {/* Acciones */}
      <div className="flex flex-wrap gap-3">
        <a
          href={outputUrl}
          download={`faceswap_${project.name ?? projectId}.mp4`}
          className="inline-flex items-center justify-center gap-2 rounded-lg text-base font-medium h-12 px-8 bg-gradient-to-r from-indigo-500 to-purple-600 text-white hover:from-indigo-600 hover:to-purple-700 shadow-lg shadow-purple-500/20 transition-all"
        >
          <Download className="h-5 w-5" />
          Descargar MP4
        </a>
        <Button variant="outline" size="lg" onClick={handleNewProject}>
          <PlusCircle className="h-4 w-4" />
          Nuevo proyecto
        </Button>
        <Button variant="ghost" size="lg" onClick={() => navigate('/projects')}>
          Mis proyectos
        </Button>
      </div>

      {/* Estadísticas */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Detalles del proyecto
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {stats.map((stat) => (
            <Card key={stat.label} className="glass">
              <CardContent className="p-3 flex items-center gap-2.5">
                <span className="text-muted-foreground shrink-0">{stat.icon}</span>
                <div className="min-w-0">
                  <p className="text-[10px] text-muted-foreground">{stat.label}</p>
                  <p className="text-sm font-semibold truncate">{stat.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Personas reemplazadas */}
      {project.detection_result && project.assignments.some((a) => a.validated) && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Reemplazos aplicados
          </h2>
          <div className="flex flex-wrap gap-3">
            {project.detection_result.persons
              .filter((p) =>
                project.assignments.find(
                  (a) => a.person_id === p.person_id && a.validated
                )
              )
              .map((person) => {
                const assignment = project.assignments.find(
                  (a) => a.person_id === person.person_id
                )
                return (
                  <div
                    key={person.person_id}
                    className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
                  >
                    <div className="h-12 w-12 rounded-lg overflow-hidden bg-muted shrink-0">
                      {person.thumbnail_url ? (
                        <img
                          src={`${BASE_URL}${person.thumbnail_url}`}
                          alt={person.label}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-muted-foreground/30 text-xs">?</div>
                      )}
                    </div>
                    <div className="text-muted-foreground text-xs px-1">→</div>
                    <div className="h-12 w-12 rounded-lg overflow-hidden bg-muted shrink-0 border border-primary/30">
                      {assignment?.photo_url ? (
                        <img
                          src={`${BASE_URL}${assignment.photo_url}`}
                          alt="Reemplazo"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-muted-foreground/30 text-xs">—</div>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold">{person.label}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {person.face_count} aparición{person.face_count !== 1 ? 'es' : ''}
                      </p>
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* Aviso */}
      <div className={cn(
        'flex items-start gap-2 text-xs text-muted-foreground rounded-lg',
        'border border-amber-500/20 bg-amber-950/10 p-4',
      )}>
        <span className="text-amber-400 text-base shrink-0">⚠</span>
        <div>
          <p className="font-medium text-amber-300/90 mb-0.5">
            Contenido generado por inteligencia artificial
          </p>
          <p>
            Este video ha sido modificado con IA. Al distribuirlo, indica claramente
            su naturaleza sintética y asegúrate de contar con los permisos necesarios.
          </p>
        </div>
      </div>
    </div>
  )
}
