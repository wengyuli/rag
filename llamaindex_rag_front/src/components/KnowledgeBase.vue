<!-- Original knowledge library by Guo Lijian; extended for asynchronous media ingestion. -->
<template>
  <div class="h-full overflow-y-auto bg-slate-50 p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="text-xs font-semibold tracking-widest text-blue-600 mb-2">{{ t('企业数字资产 AI 管理平台 · 本地资料检索') }}</p>
          <h2 class="text-2xl font-bold text-slate-800">{{ t('资料库') }}</h2>
          <p class="text-sm text-slate-500 mt-2">{{ t('统一管理选题策划文档、封面图片和拍摄与剪辑视频，处理完成后即可在 AI 查询中引用。') }}</p>
        </div>
        <button @click="fileInput?.click()" :disabled="isUploading || !canUpload"
          class="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">
          <Loader2 v-if="isUploading" class="w-4 h-4 animate-spin" /><Upload v-else class="w-4 h-4" />
          {{ t(isUploading ? '正在上传…' : user.role === 'admin' ? '上传公共资料' : '上传部门资料') }}
        </button>
        <input ref="fileInput" type="file" class="hidden" :accept="acceptedExtensions" @change="onFileChange" />
      </header>

      <div class="bg-white border border-slate-200 rounded-xl p-4 md:p-5 flex gap-3">
        <Layers3 class="w-5 h-5 mt-0.5 text-blue-600 shrink-0" />
        <div class="text-sm leading-6 text-slate-600">
          <p>{{ t('支持 PDF、Word、PPT、Excel、CSV、TXT、Markdown，JPG / PNG / WebP 图片，以及 MP4 / MOV / WebM / MKV 视频。') }}</p>
          <p>{{ t('单个文件最多 128 MB，视频最长 5 分钟。视频使用抽帧分析和语音转写，画面采样可能遗漏短暂事件。') }}</p>
          <p class="text-xs text-slate-500 mt-1">{{ t(canUpload ? (user.role === 'admin' ? '管理员上传的资料全员可见；部门成员上传的资料仅本部门可见。' : '上传的资料仅本部门可见；公共资料也可检索和预览。') : '当前账号未分配部门，请联系管理员后再上传资料。') }}</p>
        </div>
      </div>

      <p v-if="notice" role="status" class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{{ assetMessage(notice) }}</p>
      <div v-if="operationError || listError" role="alert" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex justify-between gap-3">
        <span>{{ assetMessage(operationError || listError) }}</span>
        <button v-if="listError && !operationError" @click="fetchDocuments()" class="font-semibold underline shrink-0">{{ t('重新加载') }}</button>
        <button v-else @click="operationError = ''" :aria-label="t('关闭错误提示')"><X class="w-4 h-4" /></button>
      </div>

      <div class="flex flex-wrap gap-3 items-center justify-between">
        <div class="flex flex-wrap gap-1 rounded-lg bg-slate-200/60 p-1" :aria-label="t('资料类型筛选')">
          <button v-for="filter in filters" :key="filter.id" @click="selectedType = filter.id" :aria-pressed="selectedType === filter.id"
            :class="['px-3 py-2 text-sm rounded-md transition', selectedType === filter.id ? 'bg-white shadow-sm text-blue-700 font-semibold' : 'text-slate-600 hover:bg-white/60']">
            {{ t(filter.label) }} <span class="ml-1 text-xs opacity-70">{{ number(countType(filter.id)) }}</span>
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <label class="relative">
            <Search class="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input v-model="search" :aria-label="t('按文件名称搜索')" :placeholder="t('搜索文件名称')" class="w-56 max-w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </label>
          <label>
            <span class="sr-only">{{ t('资料排序方式') }}</span>
            <select v-model="sortOrder" class="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="date">{{ t('最新上传') }}</option>
              <option value="name">{{ t('文件名称') }}</option>
              <option value="size">{{ t('文件最大') }}</option>
            </select>
          </label>
          <button @click="fetchDocuments({ silent: true })" :disabled="isLoading" :aria-label="t('刷新资料列表')" class="inline-flex items-center gap-1.5 rounded-lg px-2 py-2.5 text-sm text-slate-500 hover:bg-white hover:text-blue-600 disabled:opacity-50"><RotateCcw class="w-4 h-4" />{{ t('刷新') }}</button>
        </div>
      </div>
      <p v-if="pendingCount" class="text-xs text-slate-500 flex gap-2 items-center" role="status"><Loader2 class="w-3.5 h-3.5 animate-spin" />{{ t('{count} 份资料正在排队或处理，状态会自动更新。视频分析可能需要数分钟。', { count: number(pendingCount) }) }}</p>

      <div v-if="isLoading && !docs.length" class="bg-white border rounded-xl p-16 text-center text-slate-500"><Loader2 class="w-7 h-7 animate-spin mx-auto mb-3" />{{ t('正在加载资料…') }}</div>
      <div v-else-if="!filteredDocs.length" class="bg-white border border-dashed border-slate-300 rounded-xl px-6 py-16 text-center">
        <Database class="w-10 h-10 text-slate-300 mx-auto mb-4" />
        <h3 class="font-semibold text-slate-700">{{ t(docs.length ? '没有匹配的资料' : '从第一份资料开始') }}</h3>
        <p class="text-sm text-slate-500 mt-2">{{ t(docs.length ? '试试其他文件名或资料类型。' : '上传选题策划、封面图片或拍摄与剪辑视频，让团队从资料中找到答案。') }}</p>
      </div>
      <div v-else class="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <p>{{ t('共 {count} 份资料', { count: number(filteredDocs.length) }) }}<span v-if="filteredDocs.length !== docs.length">{{ t('，资料库总计 {count} 份', { count: number(docs.length) }) }}</span></p>
          <p class="2xl:hidden">{{ t('窄屏可横向滚动查看完整列表') }}</p>
        </div>
        <div class="overflow-x-auto focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500" role="region" :aria-label="t('资料列表，可横向滚动')" tabindex="0">
          <table class="w-full min-w-[960px] table-fixed text-left text-sm">
            <caption class="sr-only">{{ t('资料列表，包含文件名称、大小、上传时间、归属、处理状态及操作') }}</caption>
            <colgroup><col class="w-[28%]" /><col class="w-[9%]" /><col class="w-[15%]" /><col class="w-[16%]" /><col class="w-[15%]" /><col class="w-[17%]" /></colgroup>
            <thead class="bg-slate-50 text-xs text-slate-600">
              <tr>
                <th scope="col" class="px-4 py-3 font-semibold">{{ t('文件名') }}</th>
                <th scope="col" class="px-3 py-3 font-semibold">{{ t('大小') }}</th>
                <th scope="col" class="px-3 py-3 font-semibold" :title="t('按当前浏览器的本地时区显示')">{{ t('上传时间') }}</th>
                <th scope="col" class="px-3 py-3 font-semibold">{{ t('归属 / 上传者') }}</th>
                <th scope="col" class="px-3 py-3 font-semibold">{{ t('处理状态') }}</th>
                <th scope="col" class="px-4 py-3 font-semibold text-right">{{ t('操作') }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="doc in filteredDocs" :key="doc.id">
                <tr :class="['border-t border-slate-100 transition-colors', expandedIds.has(doc.id) ? 'bg-blue-50/40' : 'hover:bg-slate-50/70']">
                  <td class="px-4 py-4 align-top">
                    <div class="flex items-start gap-3">
                      <div :class="['mt-0.5 rounded-lg p-2 shrink-0', kindConfig(doc).classes]" aria-hidden="true"><component :is="kindConfig(doc).icon" class="w-4 h-4" /></div>
                      <div class="min-w-0">
                        <button @click="previewDoc = doc" :title="doc.name" :aria-label="t('预览 {name}', { name: doc.name })" class="text-left font-medium text-slate-800 leading-5 break-all line-clamp-2 hover:text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">{{ doc.name }}</button>
                        <p class="mt-1 text-xs text-slate-400">{{ t(kindConfig(doc).label) }} · {{ fileExtension(doc.name) }}<span v-if="doc.metadata?.duration_seconds"> · {{ formatTime(doc.metadata.duration_seconds) }}</span></p>
                      </div>
                    </div>
                  </td>
                  <td class="px-3 py-4 align-top text-slate-600 tabular-nums whitespace-nowrap">{{ doc.size || '—' }}</td>
                  <td class="px-3 py-4 align-top text-slate-600 tabular-nums whitespace-nowrap"><time :datetime="doc.uploaded_at || doc.date || undefined" :title="doc.uploaded_at || doc.date">{{ uploadTime(doc) }}</time></td>
                  <td class="px-3 py-4 align-top">
                    <p class="flex items-center gap-1 text-slate-600"><Globe v-if="doc.isGlobal" class="w-3.5 h-3.5 shrink-0 text-slate-400" aria-hidden="true" /><span class="truncate" :title="workspaceLabel(doc)">{{ workspaceLabel(doc) }}</span></p>
                    <p class="mt-1 text-xs text-slate-400 truncate" :title="doc.uploader_name">{{ doc.uploader_name || t('未记录上传者') }}</p>
                  </td>
                  <td class="px-3 py-4 align-top">
                    <span :class="['inline-flex text-xs rounded-full px-2 py-1 font-medium', statusConfig(doc.status).classes]">{{ t(statusConfig(doc.status).label) }}</span>
                    <div v-if="['queued', 'processing'].includes(doc.status)" class="mt-2 space-y-1.5">
                      <div class="flex items-center justify-between gap-2 text-xs text-slate-500"><span class="truncate" :title="assetMessage(doc.stage)">{{ assetMessage(doc.stage || (doc.status === 'queued' ? '等待处理' : '正在解析')) }}</span><span class="tabular-nums shrink-0">{{ progress(doc) }}%</span></div>
                      <div class="h-1 bg-slate-100 rounded-full overflow-hidden" role="progressbar" :aria-label="t('{name} 处理进度', { name: doc.name })" :aria-valuenow="progress(doc)" aria-valuemin="0" aria-valuemax="100"><div class="h-full bg-blue-500 rounded-full transition-all" :style="{ width: `${progress(doc)}%` }" /></div>
                    </div>
                    <p v-else-if="doc.error" class="mt-1.5 text-xs text-red-600 line-clamp-2 break-words" :title="assetMessage(doc.error)">{{ assetMessage(doc.error) }}</p>
                    <p v-else-if="doc.metadata?.warnings?.length" class="mt-1.5 text-xs text-amber-700">{{ t('{count} 条解析提示', { count: number(doc.metadata.warnings.length) }) }}</p>
                  </td>
                  <td class="px-4 py-4 align-top">
                    <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 text-xs">
                      <button @click="previewDoc = doc" :aria-label="t('预览原文件 {name}', { name: doc.name })" class="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800"><Eye class="w-3.5 h-3.5" aria-hidden="true" />{{ t('预览') }}</button>
                      <button v-if="hasDetails(doc)" @click="toggleDetails(doc.id)" :aria-label="t(expandedIds.has(doc.id) ? '收起 {name} 的解析详情' : '展开 {name} 的解析详情', { name: doc.name })" :aria-expanded="expandedIds.has(doc.id)" :aria-controls="`asset-detail-${doc.id}`" class="inline-flex items-center gap-1 text-slate-500 hover:text-blue-600"><ChevronDown :class="['w-3.5 h-3.5 transition-transform', expandedIds.has(doc.id) && 'rotate-180']" aria-hidden="true" />{{ t('详情') }}</button>
                      <button v-if="doc.status === 'failed' && canModify(doc)" @click="handleMutation(doc, 'retry')" :disabled="busyId === doc.id" :aria-label="t('重新处理 {name}', { name: doc.name })" class="inline-flex items-center gap-1 text-blue-600 disabled:opacity-50"><RotateCcw class="w-3.5 h-3.5" aria-hidden="true" />{{ t('重试') }}</button>
                      <button v-if="canModify(doc)" @click="handleMutation(doc, 'delete')" :disabled="doc.status === 'processing' || busyId === doc.id" :aria-label="t('删除 {name}', { name: doc.name })" :title="t(doc.status === 'processing' ? '请等待当前处理结束后再删除' : '删除 {name}', { name: doc.name })" class="inline-flex items-center gap-1 text-slate-500 hover:text-red-600 disabled:opacity-40"><Trash2 class="w-3.5 h-3.5" aria-hidden="true" />{{ t('删除') }}</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="expandedIds.has(doc.id) && hasDetails(doc)" :id="`asset-detail-${doc.id}`" class="border-t border-slate-100 bg-slate-50/80">
                  <td colspan="6" class="px-5 py-4">
                    <div class="space-y-3 max-w-4xl">
                      <div v-if="doc.error" class="text-sm text-red-700"><h4 class="font-medium mb-1">{{ t('处理失败原因') }}</h4><p class="whitespace-pre-wrap break-words leading-6">{{ assetMessage(doc.error) }}</p></div>
                      <div v-if="doc.metadata?.warnings?.length" class="text-sm text-amber-800"><h4 class="font-medium mb-1">{{ t('解析提示') }}</h4><ul class="list-disc pl-5 space-y-1 leading-6"><li v-for="(warning, index) in doc.metadata.warnings" :key="index">{{ assetMessage(warning) }}</li></ul></div>
                      <div v-if="doc.metadata?.summary" class="text-sm text-slate-600"><h4 class="font-medium mb-1 text-slate-700">{{ t('内容摘要') }}</h4><p class="whitespace-pre-wrap break-words leading-6">{{ doc.metadata.summary }}</p></div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <FilePreviewModal :is-open="Boolean(previewDoc)" :file-name="previewDoc?.name" :document-id="previewDoc?.id" :media-type="previewDoc?.media_type" :doc-workspace-id="previewDoc?.workspace_id" :user-token="user.token" @close="previewDoc = null" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Upload, Loader2, Database, Search, X, FileText, FileImage, FileVideo, Globe, Trash2, Eye, RotateCcw, Layers3, ChevronDown } from 'lucide-vue-next'
import { useDocuments } from '../composables/useDocuments'
import { useAuth } from '../composables/useAuth'
import { mediaKind, formatTime, assetMessage } from '../utils/media'
import { useI18n } from '../i18n'
import FilePreviewModal from './FilePreviewModal.vue'

const { user } = useAuth()
const { t, intlLocale, displayWorkspace } = useI18n()
const number = value => new Intl.NumberFormat(intlLocale.value).format(value)
const { docs, isUploading, isLoading, listError, uploadFile, fetchDocuments, mutateDocument } = useDocuments()
const fileInput = ref(null)
const search = ref('')
const selectedType = ref('all')
const sortOrder = ref('date')
const expandedIds = ref(new Set())
const operationError = ref('')
const notice = ref('')
const busyId = ref(null)
const previewDoc = ref(null)
const acceptedExtensions = '.pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm,.mkv'
const filters = [{ id: 'all', label: '全部' }, { id: 'document', label: '文档' }, { id: 'image', label: '图片' }, { id: 'video', label: '视频' }]
const canUpload = computed(() => user.value.role === 'admin' || (user.value.dept_id && user.value.dept_id !== 'global'))
const countType = kind => docs.value.filter(doc => kind === 'all' || mediaKind(doc) === kind).length
const pendingCount = computed(() => docs.value.filter(doc => ['queued', 'processing'].includes(doc.status)).length)
const fileExtension = name => String(name || '').split('.').pop().toUpperCase()
const workspaceLabel = doc => displayWorkspace(doc.workspace_name, doc.workspace_id) || t(doc.isGlobal ? '公共资料' : '部门资料')
const uploadTimestamp = doc => {
  const timestamp = Date.parse(doc.uploaded_at || doc.date || '')
  return Number.isNaN(timestamp) ? 0 : timestamp
}
const uploadTime = doc => {
  if (doc.uploaded_at) {
    const date = new Date(doc.uploaded_at)
    if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat(intlLocale.value, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
  }
  const parts = String(doc.date || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (parts) return new Intl.DateTimeFormat(intlLocale.value, { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3])))
  return doc.date || '—'
}
const fileBytes = doc => {
  if (doc.metadata?.size_bytes !== undefined && Number.isFinite(Number(doc.metadata.size_bytes))) return Number(doc.metadata.size_bytes)
  const match = String(doc.size || '').match(/^([\d.]+)\s*(B|KB|MB|GB)$/i)
  return match ? Number(match[1]) * (1024 ** ['B', 'KB', 'MB', 'GB'].indexOf(match[2].toUpperCase())) : 0
}
const filteredDocs = computed(() => {
  const matching = docs.value.filter(doc => (selectedType.value === 'all' || mediaKind(doc) === selectedType.value) && String(doc.name || '').toLowerCase().includes(search.value.trim().toLowerCase()))
  return matching.sort((left, right) => {
    const byName = String(left.name || '').localeCompare(String(right.name || ''), intlLocale.value, { numeric: true, sensitivity: 'base' })
    if (sortOrder.value === 'name') return byName
    if (sortOrder.value === 'size') return fileBytes(right) - fileBytes(left) || byName
    return uploadTimestamp(right) - uploadTimestamp(left) || Number(right.id) - Number(left.id) || byName
  })
})
const hasDetails = doc => Boolean(doc.error || doc.metadata?.summary || doc.metadata?.warnings?.length)
const toggleDetails = id => {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}
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
    notice.value = { key: '“{name}”已上传，正在排队处理。状态变为“可问答”后即可检索内容。', values: { name: file.name } }
    search.value = ''
    selectedType.value = 'all'
  } catch (error) {
    operationError.value = error.translation || error.message
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

const handleMutation = async (doc, action) => {
  if (action === 'delete' && !confirm(t('删除“{name}”及其检索内容？此操作无法恢复。', { name: doc.name }))) return
  operationError.value = ''
  notice.value = ''
  busyId.value = doc.id
  try {
    await mutateDocument(doc.id, action)
    notice.value = { key: action === 'retry' ? '“{name}”已重新加入处理队列。' : '“{name}”已删除。', values: { name: doc.name } }
  } catch (error) {
    operationError.value = error.translation || error.message
  } finally {
    busyId.value = null
  }
}
</script>
