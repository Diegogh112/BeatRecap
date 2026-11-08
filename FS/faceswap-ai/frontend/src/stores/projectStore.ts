import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Project,
  FaceAssignment,
  DetectionResult,
  ProcessingJob,
  UploadProgress,
} from '@/types'

interface ProjectState {
  projects: Project[]
  activeProjectId: string | null
  activeProject: Project | null
  uploadProgress: UploadProgress | null
  isUploading: boolean
  isDetecting: boolean
  detectionProgress: number
  activeJob: ProcessingJob | null

  setProjects: (projects: Project[]) => void
  addProject: (project: Project) => void
  updateProject: (project: Project) => void
  removeProject: (id: string) => void
  setActiveProject: (project: Project | null) => void
  setActiveProjectId: (id: string | null) => void
  setUploadProgress: (progress: UploadProgress | null) => void
  setIsUploading: (uploading: boolean) => void
  setIsDetecting: (detecting: boolean) => void
  setDetectionProgress: (progress: number) => void
  setDetectionResult: (result: DetectionResult) => void
  setAssignment: (assignment: FaceAssignment) => void
  removeAssignment: (personId: string) => void
  setActiveJob: (job: ProcessingJob | null) => void
  reset: () => void
}

const initialState = {
  projects: [] as Project[],
  activeProjectId: null,
  activeProject: null,
  uploadProgress: null,
  isUploading: false,
  isDetecting: false,
  detectionProgress: 0,
  activeJob: null,
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setProjects: (projects) => set({ projects }),

      addProject: (project) =>
        set((s) => ({ projects: [project, ...s.projects] })),

      updateProject: (project) =>
        set((s) => ({
          projects: s.projects.map((p) => (p.id === project.id ? project : p)),
          activeProject:
            s.activeProject?.id === project.id ? project : s.activeProject,
        })),

      removeProject: (id) =>
        set((s) => ({
          projects: s.projects.filter((p) => p.id !== id),
          activeProjectId: s.activeProjectId === id ? null : s.activeProjectId,
          activeProject: s.activeProject?.id === id ? null : s.activeProject,
        })),

      setActiveProject: (project) =>
        set({ activeProject: project, activeProjectId: project?.id ?? null }),

      setActiveProjectId: (id) => set({ activeProjectId: id }),

      setUploadProgress: (progress) => set({ uploadProgress: progress }),

      setIsUploading: (uploading) => set({ isUploading: uploading }),

      setIsDetecting: (detecting) => set({ isDetecting: detecting }),

      setDetectionProgress: (progress) => set({ detectionProgress: progress }),

      setDetectionResult: (result) =>
        set((s) => {
          if (!s.activeProject) return {}
          const updated: Project = {
            ...s.activeProject,
            status: 'detection_complete',
            detection_result: result,
            assignments: result.persons.map((p) => ({
              id: '',
              person_id: p.person_id,
              photo_url: null,
              photo_id: null,
              validated: false,
            })),
          }
          return {
            activeProject: updated,
            projects: s.projects.map((p) => (p.id === updated.id ? updated : p)),
          }
        }),

      setAssignment: (assignment) =>
        set((s) => {
          if (!s.activeProject) return {}
          const assignments = s.activeProject.assignments.map((a) =>
            a.person_id === assignment.person_id ? assignment : a
          )
          const updated: Project = { ...s.activeProject, assignments }
          return {
            activeProject: updated,
            projects: s.projects.map((p) => (p.id === updated.id ? updated : p)),
          }
        }),

      removeAssignment: (personId) => {
        const { activeProject, projects } = get()
        if (!activeProject) return
        const assignments = activeProject.assignments.map((a) =>
          a.person_id === personId
            ? { ...a, photo_url: null, photo_id: null, validated: false }
            : a
        )
        const updated: Project = { ...activeProject, assignments }
        set({
          activeProject: updated,
          projects: projects.map((p) => (p.id === updated.id ? updated : p)),
        })
      },

      setActiveJob: (job) => set({ activeJob: job }),

      reset: () => set(initialState),
    }),
    {
      name: 'faceswap-projects',
      partialize: (s) => ({
        projects: s.projects,
        activeProjectId: s.activeProjectId,
      }),
    }
  )
)
