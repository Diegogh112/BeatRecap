import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { HomePage } from '@/pages/HomePage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { UploadPage } from '@/pages/UploadPage'
import { DetectionPage } from '@/pages/DetectionPage'
import { AssignPage } from '@/pages/AssignPage'
import { ProcessingPage } from '@/pages/ProcessingPage'
import { ResultPage } from '@/pages/ResultPage'
import { useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { projectsApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { toast } from '@/hooks/useToast'

/** Ruta /project/new — crea proyecto y redirige */
function NewProjectRedirect() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setActiveProject } = useProjectStore()
  const hasFired = useRef(false)

  const mutation = useMutation({
    mutationFn: () =>
      projectsApi.create(`Proyecto ${new Date().toLocaleDateString('es')}`),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setActiveProject(project)
      navigate(`/project/${project.id}/upload`, { replace: true })
    },
    onError: (err: Error) => {
      toast({ title: 'Error al crear proyecto', description: err.message, variant: 'destructive' })
      navigate('/', { replace: true })
    },
  })

  // Lanzar la creación UNA sola vez al montar (ref evita double-fire de StrictMode)
  useEffect(() => {
    if (hasFired.current) return
    hasFired.current = true
    mutation.mutate()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        <p className="text-sm">Creando proyecto...</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/project/new" element={<NewProjectRedirect />} />
        <Route path="/project/:projectId/upload" element={<UploadPage />} />
        <Route path="/project/:projectId/detect" element={<DetectionPage />} />
        <Route path="/project/:projectId/assign" element={<AssignPage />} />
        <Route path="/project/:projectId/processing" element={<ProcessingPage />} />
        <Route path="/project/:projectId/result" element={<ResultPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
