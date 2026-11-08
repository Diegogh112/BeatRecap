import { useCallback, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import {
  User,
  Upload,
  X,
  CheckCircle2,
  AlertTriangle,
  Zap,
  ArrowLeft,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { photosApi, processingApi } from '@/services/api'
import { useProjectStore } from '@/stores/projectStore'
import { toast } from '@/hooks/useToast'
import { cn } from '@/utils/cn'
import type { DetectedPerson, FaceAssignment } from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

const ACCEPTED_PHOTO_TYPES = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
}

interface PersonCardProps {
  person: DetectedPerson
  assignment: FaceAssignment | undefined
  projectId: string
  onAssigned: (assignment: FaceAssignment) => void
  onRemoved: (personId: string) => void
}

function PersonCard({ person, assignment, projectId, onAssigned, onRemoved }: PersonCardProps) {
  const [localPreview, setLocalPreview] = useState<string | null>(
    assignment?.photo_url ?? null
  )
  const [isUploading, setIsUploading] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => photosApi.upload(projectId, person.person_id, file),
    onSuccess: (result) => {
      setIsUploading(false)
      onAssigned({
        id: '',
        person_id: person.person_id,
        photo_url: result.url,
        photo_id: result.photoId,
        validated: result.validated,
      })
      if (!result.validated) {
        toast({
          title: 'Advertencia',
          description: 'No se detectó un rostro claro en la fotografía.',
          variant: 'warning',
        })
      } else {
        toast({ title: `Foto asignada a ${person.label}`, variant: 'success' })
      }
    },
    onError: (err: Error) => {
      setIsUploading(false)
      toast({ title: 'Error', description: err.message, variant: 'destructive' })
    },
  })

  const onDrop = useCallback(
    (files: File[]) => {
      const file = files[0]
      if (!file) return
      const preview = URL.createObjectURL(file)
      setLocalPreview(preview)
      setIsUploading(true)
      uploadMutation.mutate(file)
    },
    [person.person_id]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_PHOTO_TYPES,
    maxFiles: 1,
    disabled: isUploading,
  })

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (localPreview && !localPreview.startsWith('http')) URL.revokeObjectURL(localPreview)
    setLocalPreview(null)
    onRemoved(person.person_id)
  }

  const photoSrc = localPreview
    ? localPreview.startsWith('http') || localPreview.startsWith('blob')
      ? localPreview
      : `${BASE_URL}${localPreview}`
    : null

  return (
    <Card className="glass overflow-hidden">
      <CardContent className="p-4 space-y-3">
        {/* Persona detectada */}
        <div className="flex items-center gap-3">
          <div className="h-12 w-12 rounded-xl overflow-hidden bg-muted shrink-0">
            {person.thumbnail_url ? (
              <img
                src={`${BASE_URL}${person.thumbnail_url}`}
                alt={person.label}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <User className="h-6 w-6 text-muted-foreground/40" />
              </div>
            )}
          </div>
          <div>
            <p className="font-semibold text-sm">{person.label}</p>
            <p className="text-xs text-muted-foreground">
              {person.face_count} aparición{person.face_count !== 1 ? 'es' : ''}
            </p>
          </div>
          {assignment?.validated && (
            <Badge variant="success" className="ml-auto">
              <CheckCircle2 className="h-3 w-3" /> Lista
            </Badge>
          )}
        </div>

        {/* Flecha de comparación */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-px bg-border" />
          <span className="text-xs text-muted-foreground px-1">reemplazar por →</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Zona de carga de foto de reemplazo */}
        {photoSrc ? (
          <div className="relative">
            <div className="h-32 rounded-xl overflow-hidden bg-muted">
              <img
                src={photoSrc}
                alt="Reemplazo"
                className="w-full h-full object-cover"
              />
            </div>
            {assignment && !assignment.validated && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-400">
                <AlertTriangle className="h-3 w-3" />
                Rostro no detectado. Prueba con otra foto.
              </div>
            )}
            <div className="flex gap-2 mt-2">
              <div
                {...getRootProps()}
                className="flex-1 flex items-center justify-center gap-1 text-xs text-muted-foreground border border-dashed border-border rounded-lg py-2 cursor-pointer hover:border-primary/50 hover:text-primary transition-colors"
              >
                <input {...getInputProps()} />
                <Upload className="h-3 w-3" /> Cambiar foto
              </div>
              <button
                onClick={handleRemove}
                className="px-3 py-2 rounded-lg border border-border text-muted-foreground hover:text-destructive hover:border-destructive/50 transition-colors"
                aria-label="Eliminar foto"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={cn(
              'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-all',
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50 hover:bg-accent/30',
              isUploading && 'opacity-50 cursor-wait'
            )}
          >
            <input {...getInputProps()} />
            {isUploading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Zap className="h-4 w-4 animate-pulse text-primary" />
                Subiendo...
              </div>
            ) : (
              <>
                <Upload className="h-6 w-6 text-muted-foreground/50" />
                <p className="text-xs text-muted-foreground">
                  Arrastra o haz clic para cargar
                  <br />
                  <span className="opacity-60">JPG, PNG o WEBP</span>
                </p>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function AssignPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const {
    activeProject,
    setAssignment,
    removeAssignment,
    updateProject,
    setActiveJob,
  } = useProjectStore()

  const result = activeProject?.detection_result
  const assignments = activeProject?.assignments ?? []

  const validAssignments = assignments.filter((a) => a.validated && a.photo_id)

  const processMutation = useMutation({
    mutationFn: () => {
      const assignMap: Record<string, string> = {}
      for (const a of validAssignments) {
        assignMap[a.person_id] = a.photo_id!
      }
      return processingApi.start(projectId!, assignMap)
    },
    onSuccess: () => {
      // Limpiar el job anterior para que ProcessingPage no muestre "completado" de un run previo
      setActiveJob(null)
      if (activeProject) {
        updateProject({ ...activeProject, status: 'queued' })
      }
      navigate(`/project/${projectId}/processing`)
    },
    onError: (err: Error) =>
      toast({ title: 'Error al iniciar procesamiento', description: err.message, variant: 'destructive' }),
  })

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-muted-foreground">No hay resultados de detección.</p>
        <Button
          className="mt-4"
          variant="outline"
          onClick={() => navigate(`/project/${projectId}/detect`)}
        >
          Volver a detección
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {['Cargar video', 'Detectar rostros', 'Asignar reemplazos', 'Procesar'].map((step, i) => (
          <span key={step} className="flex items-center gap-1">
            {i > 0 && <span className="text-border">›</span>}
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold',
              i === 2 ? 'bg-primary text-primary-foreground' : i < 2 ? 'bg-muted' : ''
            )}>
              {i + 1}
            </span>
            <span className={i < 2 ? 'line-through opacity-50' : i === 2 ? '' : 'opacity-50'}>
              {step}
            </span>
          </span>
        ))}
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Asignar reemplazos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Carga una fotografía para cada persona que deseas reemplazar.
            Puedes reemplazar una, varias o todas.
          </p>
        </div>
        <Badge variant="purple">
          {validAssignments.length}/{result.persons.length} asignada
          {validAssignments.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {/* Grid de personas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {result.persons.map((person) => (
          <PersonCard
            key={person.person_id}
            person={person}
            assignment={assignments.find((a) => a.person_id === person.person_id)}
            projectId={projectId!}
            onAssigned={(a) => setAssignment(a)}
            onRemoved={(id) => removeAssignment(id)}
          />
        ))}
      </div>

      {/* Resumen y acción */}
      {validAssignments.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-950/10 px-4 py-3 text-sm text-amber-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Debes asignar al menos una fotografía de reemplazo para continuar.
        </div>
      )}

      <div className="flex gap-3">
        <Button
          variant="gradient"
          size="lg"
          loading={processMutation.isPending}
          disabled={validAssignments.length === 0}
          onClick={() => processMutation.mutate()}
        >
          <Zap className="h-5 w-5" />
          Generar video ({validAssignments.length} reemplazo
          {validAssignments.length !== 1 ? 's' : ''})
        </Button>
        <Button
          variant="outline"
          size="lg"
          onClick={() => navigate(`/project/${projectId}/detect`)}
        >
          <ArrowLeft className="h-4 w-4" /> Volver
        </Button>
      </div>
    </div>
  )
}
