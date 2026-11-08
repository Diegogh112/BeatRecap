import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusCircle,
  Video,
  Clock,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Trash2,
  ChevronRight,
  Zap,
  Users,
  Cpu,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { projectsApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { formatDate } from '@/utils/format'
import { toast } from '@/hooks/useToast'
import type { Project, ProjectStatus } from '@/types'

const statusConfig: Record<
  ProjectStatus,
  { label: string; variant: 'default' | 'success' | 'warning' | 'info' | 'destructive' | 'purple'; icon: React.ReactNode }
> = {
  created:            { label: 'Creado',             variant: 'default',     icon: <Clock className="h-3 w-3" /> },
  video_uploaded:     { label: 'Video cargado',      variant: 'info',        icon: <Video className="h-3 w-3" /> },
  detecting:          { label: 'Detectando',         variant: 'warning',     icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  detection_complete: { label: 'Detección lista',    variant: 'purple',      icon: <Users className="h-3 w-3" /> },
  assigning:          { label: 'Configurando',       variant: 'purple',      icon: <Users className="h-3 w-3" /> },
  queued:             { label: 'En cola',            variant: 'warning',     icon: <Clock className="h-3 w-3" /> },
  processing:         { label: 'Procesando',         variant: 'warning',     icon: <Cpu className="h-3 w-3 animate-pulse" /> },
  completed:          { label: 'Completado',         variant: 'success',     icon: <CheckCircle2 className="h-3 w-3" /> },
  error:              { label: 'Error',              variant: 'destructive', icon: <AlertCircle className="h-3 w-3" /> },
}

export function HomePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setActiveProject } = useProjectStore()

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      projectsApi.create(`Proyecto ${new Date().toLocaleDateString('es')}`),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setActiveProject(project)
      navigate(`/project/${project.id}/upload`)
    },
    onError: (err: Error) =>
      toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  })

  const deleteMutation = useMutation({
    mutationFn: projectsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      toast({ title: 'Proyecto eliminado', variant: 'default' })
    },
  })

  const openProject = (project: Project) => {
    setActiveProject(project)
    const routes: Partial<Record<ProjectStatus, string>> = {
      created:            `/project/${project.id}/upload`,
      video_uploaded:     `/project/${project.id}/upload`,
      detecting:          `/project/${project.id}/detect`,
      detection_complete: `/project/${project.id}/assign`,
      assigning:          `/project/${project.id}/assign`,
      queued:             `/project/${project.id}/processing`,
      processing:         `/project/${project.id}/processing`,
      completed:          `/project/${project.id}/result`,
      error:              `/project/${project.id}/upload`,
    }
    navigate(routes[project.status] ?? `/project/${project.id}/upload`)
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-indigo-950/50 via-purple-950/30 to-background p-8 md:p-12">
        <div className="relative z-10 max-w-2xl">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <Badge variant="purple">IA en tiempo real</Badge>
          </div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight mb-3">
            Intercambio de rostros{' '}
            <span className="text-gradient">potenciado por IA</span>
          </h1>
          <p className="text-muted-foreground text-lg mb-6 leading-relaxed">
            Sube un video, detecta automáticamente todas las personas y reemplaza
            sus rostros con fotografías de tu elección. Soporta múltiples personas
            y videos de hasta 5 minutos.
          </p>
          <Button
            size="lg"
            variant="gradient"
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            <PlusCircle className="h-5 w-5" />
            Nuevo proyecto
          </Button>
        </div>
        {/* Decoración de fondo */}
        <div className="absolute right-0 top-0 h-full w-1/2 opacity-10 pointer-events-none select-none">
          <div className="absolute top-8 right-8 h-48 w-48 rounded-full bg-purple-500 blur-3xl" />
          <div className="absolute bottom-8 right-32 h-32 w-32 rounded-full bg-indigo-500 blur-3xl" />
        </div>
      </div>

      {/* Features rápidas */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: <Video className="h-5 w-5 text-indigo-400" />,
            title: 'Hasta 5 minutos',
            desc: 'MP4, MOV y AVI. Validación automática de formato y duración.',
          },
          {
            icon: <Users className="h-5 w-5 text-purple-400" />,
            title: 'Múltiples personas',
            desc: 'Detecta y agrupa automáticamente todas las identidades del video.',
          },
          {
            icon: <Cpu className="h-5 w-5 text-pink-400" />,
            title: 'Motor de IA real',
            desc: 'InsightFace + InSwapper + GFPGAN. No superposición de imágenes.',
          },
        ].map((f) => (
          <Card key={f.title} className="glass">
            <CardContent className="pt-6 flex gap-4">
              <div className="mt-0.5">{f.icon}</div>
              <div>
                <p className="font-semibold text-sm mb-1">{f.title}</p>
                <p className="text-xs text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Lista de proyectos */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Proyectos recientes</h2>
          <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
            Ver todos <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : !projects?.length ? (
          <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-border rounded-xl">
            <Video className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground font-medium">Sin proyectos todavía</p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Crea tu primer proyecto para comenzar
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.slice(0, 5).map((project) => {
              const cfg = statusConfig[project.status]
              return (
                <div
                  key={project.id}
                  className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 hover:bg-accent/30 transition-colors cursor-pointer group"
                  onClick={() => openProject(project)}
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Video className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{project.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDate(project.created_at)}
                    </p>
                  </div>
                  <Badge variant={cfg.variant as never} className="shrink-0 hidden sm:flex">
                    {cfg.icon}
                    {cfg.label}
                  </Badge>
                  <button
                    className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md hover:bg-destructive/20 text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteMutation.mutate(project.id)
                    }}
                    aria-label="Eliminar proyecto"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors shrink-0" />
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
