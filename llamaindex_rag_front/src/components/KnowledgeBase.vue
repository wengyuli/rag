<!-- Original knowledge library by Guo Lijian; extended for asynchronous media ingestion. -->
<template>
  <div class="h-full overflow-y-auto bg-slate-50 p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="text-xs font-semibold tracking-widest text-blue-600 mb-2">星河内容工作室 · 本地资料检索</p>
          <h2 class="text-2xl font-bold text-slate-800">资料库</h2>
          <p class="text-sm text-slate-500 mt-2">统一管理选题策划文档、封面图片和拍摄与剪辑视频，处理完成后即可在智能问答中引用。</p>
        </div>
        <button @click="fileInput?.click()" :disabled="isUploading || !canUpload"
          class="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">
          <Loader2 v-if="isUploading" class="w-4 h-4 animate-spin" /><Upload v-else class="w-4 h-4" />
          {{ isUploading ? '正在上传…' : user.role === 'admin' ? '上传公共资料' : '上传部门资料' }}
        </button>
        <input ref="fileInput" type="file" class="hidden" :accept="acceptedExtensions" @change="onFileChange" />
      </header>

      <div class="bg-white border border-slate-200 rounded-xl p-4 md:p-5 flex gap-3">
        <Layers3 class="w-5 h-5 mt-0.5 text-blue-600 shrink-0" />
        <div class="text-sm leading-6 text-slate-600">
          <p>支持 PDF、Word、PPT、Excel、CSV、TXT、Markdown，JPG / PNG / WebP 图片，以及 MP4 / MOV / WebM / MKV 视频。</p>
          <p>单个文件最多 128 MB，视频最长 5 分钟。视频使用抽帧分析和语音转写，画面采样可能遗漏短暂事件。</p>
          <p class="text-xs text-slate-500 mt-1">{{ canUpload ? (user.role === 'admin' ? '管理员上传的资料全员可见；部门成员上传的资料仅本部门可见。' : '上传的资料仅本部门可见；公共资料也可检索和预览。') : '当前账号未分配部门，请联系管理员后再上传资料。' }}</p>
        </div>
      </div>

      <p v-if="notice" role="status" class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{{ notice }}</p>
      <div v-if="operationError || listError" role="alert" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex justify-between gap-3">
        <span>{{ operationError || listError }}</span>
        <button v-if="listError && !operationError" @click="fetchDocuments()" class="font-semibold underline shrink-0">重新加载</button>
        <button v-else @click="operationError = ''" aria-label="关闭错误提示"><X class="w-4 h-4" /></button>
      </div>

      <div class="flex flex-wrap gap-3 items-center justify-between">
        <div class="flex flex-wrap gap-1 rounded-lg bg-slate-200/60 p-1" aria-label="资料类型筛选">
          <button v-for="filter in filters" :key="filter.id" @click="selectedType = filter.id" :aria-pressed="selectedType === filter.id"
            :class="['px-3 py-2 text-sm rounded-md transition', selectedType === filter.id ? 'bg-white shadow-sm text-blue-700 font-semibold' : 'text-slate-600 hover:bg-white/60']">
            {{ filter.label }} <span class="ml-1 text-xs opacity-70">{{ countType(filter.id) }}</span>
          </button>
        </div>
        <button @click="fetchDocuments({ silent: true })" :disabled="isLoading" aria-label="刷新资料列表" class="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 disabled:opacity-50"><RotateCcw class="w-4 h-4" />刷新</button>
        <label class="relative flex-1 max-w-xs min-w-48">
          <Search class="w-4 h-4 absolute left-3 top-3 text-slate-400" />
          <input v-model="search" aria-label="按文件名称搜索" placeholder="搜索文件名称" class="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </label>
      </div>
      <p v-if="pendingCount" class="text-xs text-slate-500 flex gap-2 items-center" role="status"><Loader2 class="w-3.5 h-3.5 animate-spin" />{{ pendingCount }} 份资料正在排队或处理，状态会自动更新。视频分析可能需要数分钟。</p>

      <div v-if="isLoading && !docs.length" class="bg-white border rounded-xl p-16 text-center text-slate-500"><Loader2 class="w-7 h-7 animate-spin mx-auto mb-3" />正在加载资料…</div>
      <div v-else-if="!filteredDocs.length" class="bg-white border border-dashed border-slate-300 rounded-xl px-6 py-16 text-center">
        <Database class="w-10 h-10 text-slate-300 mx-auto mb-4" />
        <h3 class="font-semibold text-slate-700">{{ docs.length ? '没有匹配的资料' : '从第一份资料开始' }}</h3>
        <p class="text-sm text-slate-500 mt-2">{{ docs.length ? '试试其他文件名或资料类型。' : '上传选题策划、封面图片或拍摄与剪辑视频，让团队从资料中找到答案。' }}</p>
      </div>
      <div v-else class="grid gap-4 lg:grid-cols-2">
        <article v-for="doc in filteredDocs" :key="doc.id" class="bg-white border border-slate-200 rounded-xl p-5 flex flex-col min-w-0">
          <div class="flex gap-3 items-start">
            <div :class="['rounded-lg p-2.5 shrink-0', kindConfig(doc).classes]"><component :is="kindConfig(doc).icon" class="w-5 h-5" /></div>
            <div class="min-w-0 flex-1">
              <button @click="previewDoc = doc" class="font-semibold text-slate-800 hover:text-blue-700 text-left break-all leading-6">{{ doc.name }}</button>
              <p class="text-xs text-slate-500 mt-1">{{ kindConfig(doc).label }} · {{ doc.size }}<span v-if="doc.metadata?.duration_seconds"> · {{ formatTime(doc.metadata.duration_seconds) }}</span> · {{ doc.date }}</p>
            </div>
            <span :class="['text-xs rounded-full px-2 py-1 shrink-0 font-medium', statusConfig(doc.status).classes]">{{ statusConfig(doc.status).label }}</span>
          </div>
          <div class="mt-3 flex flex-wrap gap-2 items-center text-xs text-slate-500">
            <span class="flex items-center gap-1 rounded bg-slate-100 px-2 py-1"><Globe v-if="doc.isGlobal" class="w-3 h-3" />{{ doc.workspace_name || (doc.isGlobal ? '公共资料' : '部门资料') }}</span>
            <span v-if="doc.uploader_name">{{ doc.uploader_name }} 上传</span>
          </div>
          <div v-if="['queued', 'processing'].includes(doc.status)" class="mt-4">
            <div class="flex justify-between text-xs text-slate-500 mb-2"><span>{{ doc.stage || (doc.status === 'queued' ? '等待处理' : '正在解析内容') }}</span><span>{{ progress(doc) }}%</span></div>
            <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden" role="progressbar" :aria-label="`${doc.name} 处理进度`" :aria-valuenow="progress(doc)" aria-valuemin="0" aria-valuemax="100"><div class="h-full bg-blue-500 rounded-full transition-all" :style="{ width: `${progress(doc)}%` }" /></div>
          </div>
          <p v-if="doc.error" class="text-sm text-red-700 bg-red-50 rounded-lg p-3 mt-3 break-words">{{ doc.error }}</p>
          <p v-if="doc.metadata?.summary" class="text-sm text-slate-600 mt-3 leading-6 line-clamp-3" :title="doc.metadata.summary">{{ doc.metadata.summary }}</p>
          <details v-if="doc.metadata?.warnings?.length" class="text-xs text-amber-800 bg-amber-50 rounded-lg p-3 mt-3">
            <summary class="cursor-pointer font-medium">解析提示（{{ doc.metadata.warnings.length }}）</summary>
            <ul class="list-disc pl-4 mt-2 space-y-1"><li v-for="(warning, index) in doc.metadata.warnings" :key="index">{{ warning }}</li></ul>
          </details>
          <div class="flex justify-end gap-3 items-center border-t border-slate-100 pt-3 mt-4 text-sm">
            <button @click="previewDoc = doc" class="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800"><Eye class="w-4 h-4" />预览</button>
            <button v-if="doc.status === 'failed' && canModify(doc)" @click="handleMutation(doc, 'retry')" :disabled="busyId === doc.id" class="inline-flex items-center gap-1 text-blue-600 disabled:opacity-50"><RotateCcw class="w-4 h-4" />重新处理</button>
            <button v-if="canModify(doc)" @click="handleMutation(doc, 'delete')" :disabled="doc.status === 'processing' || busyId === doc.id" :title="doc.status === 'processing' ? '请等待当前处理结束后再删除' : '删除资料'" class="inline-flex items-center gap-1 text-slate-500 hover:text-red-600 disabled:opacity-40"><Trash2 class="w-4 h-4" />删除</button>
          </div>
        </article>
      </div>
    </div>
    <FilePreviewModal :is-open="Boolean(previewDoc)" :file-name="previewDoc?.name" :document-id="previewDoc?.id" :media-type="previewDoc?.media_type" :doc-workspace-id="previewDoc?.workspace_id" :user-token="user.token" @close="previewDoc = null" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Upload, Loader2, Database, Search, X, FileText, FileImage, FileVideo, Globe, Trash2, Eye, RotateCcw, Layers3 } from 'lucide-vue-next'
import { useDocuments } from '../composables/useDocuments'
import { useAuth } from '../composables/useAuth'
import { mediaKind, formatTime } from '../utils/media'
import FilePreviewModal from './FilePreviewModal.vue'

const { user } = useAuth()
const { docs, isUploading, isLoading, listError, uploadFile, fetchDocuments, mutateDocument } = useDocuments()
const fileInput = ref(null)
const search = ref('')
const selectedType = ref('all')
const operationError = ref('')
const notice = ref('')
const busyId = ref(null)
const previewDoc = ref(null)
const acceptedExtensions = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm,.mkv'
const filters = [{ id: 'all', label: '全部' }, { id: 'document', label: '文档' }, { id: 'image', label: '图片' }, { id: 'video', label: '视频' }]
const canUpload = computed(() => user.value.role === 'admin' || (user.value.dept_id && user.value.dept_id !== 'global'))
const countType = kind => docs.value.filter(doc => kind === 'all' || mediaKind(doc) === kind).length
const pendingCount = computed(() => docs.value.filter(doc => ['queued', 'processing'].includes(doc.status)).length)
const filteredDocs = computed(() => docs.value.filter(doc => (selectedType.value === 'all' || mediaKind(doc) === selectedType.value) && doc.name.toLowerCase().includes(search.value.trim().toLowerCase())))
const kindConfig = doc => ({
  document: { label: '文档', icon: FileText, classes: 'bg-blue-50 text-blue-600' },
  image: { label: '图片', icon: FileImage, classes: 'bg-purple-50 text-purple-600' },
  video: { label: '视频', icon: FileVideo, classes: 'bg-amber-50 text-amber-700' },
}[mediaKind(doc)] || { label: '资料', icon: FileText, classes: 'bg-slate-100 text-slate-500' })
const statusConfig = status => ({
  indexed: { label: '可问答', classes: 'bg-emerald-50 text-emerald-700' },
  queued: { label: '排队中', classes: 'bg-slate-100 text-slate-600' },
  processing: { label: '处理中', classes: 'bg-blue-50 text-blue-700' },
  failed: { label: '处理失败', classes: 'bg-red-50 text-red-700' },
}[status] || { label: status || '未知状态', classes: 'bg-slate-100 text-slate-600' })
const progress = doc => Math.max(0, Math.min(100, Math.round(Number(doc.progress) || 0)))
const canModify = doc => user.value.role === 'admin' || (!doc.isGlobal && String(doc.workspace_id) === String(user.value.dept_id))

const onFileChange = async event => {
  const file = event.target.files?.[0]
  if (!file) return
  operationError.value = ''
  notice.value = ''
  try {
    if (file.size > 128 * 1024 * 1024) throw new Error('文件超过 128 MB，请压缩文件或拆分视频后上传。')
    const extension = '.' + file.name.split('.').pop().toLowerCase()
    if (!acceptedExtensions.split(',').includes(extension)) throw new Error('暂不支持此文件格式，请选择上方列出的格式。')
    await uploadFile(file, user.value.role === 'admin')
    notice.value = `“${file.name}”已上传，正在排队处理。状态变为“可问答”后即可检索内容。`
    search.value = ''
    selectedType.value = 'all'
  } catch (error) {
    operationError.value = error.message
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

const handleMutation = async (doc, action) => {
  if (action === 'delete' && !confirm(`删除“${doc.name}”及其检索内容？此操作无法恢复。`)) return
  operationError.value = ''
  notice.value = ''
  busyId.value = doc.id
  try {
    await mutateDocument(doc.id, action)
    notice.value = action === 'retry' ? `“${doc.name}”已重新加入处理队列。` : `“${doc.name}”已删除。`
  } catch (error) {
    operationError.value = error.message
  } finally {
    busyId.value = null
  }
}
</script>
