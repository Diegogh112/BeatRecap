import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusCircle,
  Video,
  Loader2,
  Trash2,
  ChevronRight,
  Search,
} from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { projectsApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { formatDate } from '@/utils/format'
import { toast } from '@/hooks/useToast'
import type { Project, ProjectStatus } from '@/types'

const statusLabels: Record<ProjectStatus, string> = {
  created: 'Creado',
  video_uploaded: 'Video cargado',
  detecting: 'Detectando',
  detection_complete: 'Detección lista',
  assigning: 'Configurando',
  queued: 'En cola',
  processing: 'Procesando',
  completed: 'Completado',
  error: 'Error',
}

const statusVariant: Record<ProjectStatus, string> = {
  created: 'default',
  video_uploaded: 'info',
  detecting: 'warning',
  detection_complete: 'purple',
  assigning: 'purple',
  queued: 'warning',
  processing: 'warning',
  completed: 'success',
  error: 'destructive',
}

export function ProjectsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setActiveProject } = useProjectStore()
  const [search, setSearch] = useState('')

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
      toast({ title: 'Proyecto eliminado' })
    },
  })

  const openProject = (project: Project) => {
    setActiveProject(project)
    const routes: Partial<Record<ProjectStatus, string>> = {
      created: `/project/${project.id}/upload`,
      video_uploaded: `/project/${project.id}/upload`,
      detecting: `/project/${project.id}/detect`,
      detection_complete: `/project/${project.id}/assign`,
      assigning: `/project/${project.id}/assign`,
      queued: `/project/${project.id}/processing`,
      processing: `/project/${project.id}/processing`,
      completed: `/project/${project.id}/result`,
      error: `/project/${project.id}/upload`,
    }
    navigate(routes[project.status] ?? `/project/${project.id}/upload`)
  }

  const filtered = projects?.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mis proyectos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {projects?.length ?? 0} proyecto{projects?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          variant="gradient"
          loading={createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          <PlusCircle className="h-4 w-4" />
          Nuevo
        </Button>
      </div>

      {/* Buscador */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-border bg-card text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          placeholder="Buscar proyectos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !filtered?.length ? (
        <div className="flex flex-col items-center justify-center py-24 text-center border border-dashed border-border rounded-xl">
          <Video className="h-12 w-12 text-muted-foreground/20 mb-4" />
          <p className="font-medium text-muted-foreground">
            {search ? 'Sin resultados' : 'Sin proyectos'}
          </p>
          {!search && (
            <p className="text-sm text-muted-foreground/60 mt-1 mb-4">
              Crea tu primer proyecto para empezar
            </p>
          )}
          {!search && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => createMutation.mutate()}
            >
              <PlusCircle className="h-4 w-4" /> Crear proyecto
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((project) => (
            <div
              key={project.id}
              className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 hover:bg-accent/30 transition-colors cursor-pointer group"
              onClick={() => openProject(project)}
            >
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted">
                <Video className="h-6 w-6 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm truncate">{project.name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDate(project.created_at)}
                </p>
                {project.detection_result && (
                  <p className="text-xs text-muted-foreground/60 mt-0.5">
                    {project.detection_result.total_persons} persona
                    {project.detection_result.total_persons !== 1 ? 's' : ''} detectada
                    {project.detection_result.total_persons !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
              <Badge
                variant={statusVariant[project.status] as never}
                className="shrink-0 hidden sm:flex"
              >
                {statusLabels[project.status]}
              </Badge>
              <button
                className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded-md hover:bg-destructive/20 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm('¿Eliminar este proyecto?'))
                    deleteMutation.mutate(project.id)
                }}
                aria-label="Eliminar proyecto"
              >
                <Trash2 className="h-4 w-4" />
              </button>
              <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
