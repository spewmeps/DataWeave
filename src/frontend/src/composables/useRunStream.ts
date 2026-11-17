import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

const RUN_EVENTS = [
  'run.created',
  'run.status.changed',
  'task.status.changed',
  'task.completed',
  'run.awaiting_review',
  'run.published',
]

export function useRunStream(runId: Ref<string | null>, onUpdate: () => void) {
  const connectionState = ref<'idle' | 'connecting' | 'live' | 'polling'>('idle')
  let source: EventSource | null = null
  let pollTimer: number | null = null
  let refreshTimer: number | null = null

  function requestRefresh() {
    if (refreshTimer !== null) return
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null
      onUpdate()
    }, 80)
  }

  function startPolling() {
    if (pollTimer !== null) return
    connectionState.value = 'polling'
    pollTimer = window.setInterval(onUpdate, 1500)
  }

  function stop() {
    source?.close()
    source = null
    if (pollTimer !== null) window.clearInterval(pollTimer)
    if (refreshTimer !== null) window.clearTimeout(refreshTimer)
    pollTimer = null
    refreshTimer = null
  }

  function connect(id: string) {
    stop()
    connectionState.value = 'connecting'
    source = new EventSource(`/api/runs/${id}/events`)
    source.onopen = () => {
      connectionState.value = 'live'
      if (pollTimer !== null) window.clearInterval(pollTimer)
      pollTimer = null
    }
    for (const eventName of RUN_EVENTS) source.addEventListener(eventName, requestRefresh)
    source.onerror = () => {
      source?.close()
      source = null
      startPolling()
    }
    requestRefresh()
  }

  watch(runId, (id) => (id ? connect(id) : stop()), { immediate: true })
  onBeforeUnmount(stop)

  return { connectionState, stop }
}

