import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { Project, Run } from '../types'

export const useWorkbenchStore = defineStore('workbench', () => {
  const projects = ref<Project[]>([])
  const project = ref<Project | null>(null)
  const run = ref<Run | null>(null)
  const selectedRunId = ref('')
  const loading = ref(false)
  const error = ref('')
  const connected = ref(false)
  let socket: WebSocket | null = null

  const latestRun = computed(() => run.value)

  async function loadProjects() {
    projects.value = await api<Project[]>('/api/v1/projects')
  }

  async function loadProject(projectId: string, preferredRunId?: string) {
    loading.value = true
    error.value = ''
    try {
      project.value = await api<Project>(`/api/v1/projects/${projectId}`)
      const requestedRunId = preferredRunId || selectedRunId.value
      const runId = project.value.runs?.some((item) => item.id === requestedRunId)
        ? requestedRunId
        : project.value.runs?.[0]?.id
      selectedRunId.value = runId || ''
      run.value = runId ? await api<Run>(`/api/v1/runs/${runId}`) : null
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : String(reason)
    } finally {
      loading.value = false
    }
  }

  async function selectRun(runId: string) {
    selectedRunId.value = runId
    run.value = await api<Run>(`/api/v1/runs/${runId}`)
  }

  function connectEvents(projectId: string) {
    socket?.close()
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${location.host}/ws/v1/events`)
    socket.onopen = () => { connected.value = true }
    socket.onclose = () => { connected.value = false }
    socket.onmessage = async (event) => {
      const message = JSON.parse(event.data)
      if (['run.progress', 'run.completed', 'task.completed', 'capture.updated'].includes(message.event)) {
        await loadProject(projectId)
      }
    }
  }

  return {
    projects,
    project,
    run,
    selectedRunId,
    latestRun,
    loading,
    error,
    connected,
    loadProjects,
    loadProject,
    selectRun,
    connectEvents,
  }
})
