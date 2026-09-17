/** Enterprise asset upload and processing status polling. Original document module by Guo Lijian. */
import { ref, watch, onScopeDispose, onActivated, onDeactivated } from 'vue'
import { useWorkspace } from './useWorkspace'
import { useAuth } from './useAuth'

export function useDocuments() {
  const { user } = useAuth()
  const { currentWorkspace } = useWorkspace()
  const docs = ref([])
  const isUploading = ref(false)
  const isLoading = ref(false)
  const listError = ref('')
  let pollTimer
  let listController
  let disposed = false
  let active = true

  const readError = async (response, fallback) => {
    const data = await response.json().catch(() => null)
    const key = typeof data?.detail === 'string' ? data.detail : `${fallback}（HTTP {status}）`
    return Object.assign(new Error(key), { translation: { key, values: { status: response.status } } })
  }

  const fetchDocuments = async ({ silent = false } = {}) => {
    clearTimeout(pollTimer)
    listController?.abort()
    if (disposed || !active || !user.value.token) return
    const controller = new AbortController()
    listController = controller
    if (!silent) isLoading.value = true
    try {
      const workspace = currentWorkspace.value?.id || 'global'
      const response = await fetch(`/api/documents?workspace_id=${encodeURIComponent(workspace)}`, {
        headers: { Authorization: `Bearer ${user.value.token}` },
        signal: controller.signal,
      })
      if (!response.ok) throw await readError(response, '获取资料列表失败')
      const data = await response.json()
      if (controller.signal.aborted || disposed) return
      docs.value = data
      listError.value = ''
    } catch (error) {
      if (error.name !== 'AbortError' && !disposed) listError.value = error.translation || error.message
    } finally {
      if (listController === controller && !disposed && active) {
        isLoading.value = false
        if (docs.value.some(doc => ['queued', 'processing'].includes(doc.status))) {
          pollTimer = setTimeout(() => fetchDocuments({ silent: true }), 4000)
        }
      }
    }
  }

  const uploadFile = async (file, isPublic = false) => {
    isUploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('is_public', String(isPublic))
      const response = await fetch('/api/documents/upload', {
        method: 'POST', headers: { Authorization: `Bearer ${user.value.token}` }, body: formData,
      })
      if (!response.ok) throw await readError(response, '上传失败')
      const result = await response.json()
      await fetchDocuments({ silent: true })
      return result
    } finally {
      isUploading.value = false
    }
  }

  const mutateDocument = async (id, action) => {
    const response = await fetch(`/api/documents/${encodeURIComponent(id)}${action === 'retry' ? '/retry' : ''}`, {
      method: action === 'retry' ? 'POST' : 'DELETE',
      headers: { Authorization: `Bearer ${user.value.token}` },
    })
    if (!response.ok) throw await readError(response, action === 'retry' ? '重试失败' : '删除失败')
    await fetchDocuments({ silent: true })
  }

  watch(() => currentWorkspace.value?.id, () => {
    docs.value = []
    fetchDocuments()
  }, { immediate: true })

  onActivated(() => {
    active = true
    fetchDocuments({ silent: docs.value.length > 0 })
  })
  onDeactivated(() => {
    active = false
    clearTimeout(pollTimer)
    listController?.abort()
    isLoading.value = false
  })

  onScopeDispose(() => {
    disposed = true
    clearTimeout(pollTimer)
    listController?.abort()
  })

  return { docs, isUploading, isLoading, listError, uploadFile, fetchDocuments, mutateDocument }
}
