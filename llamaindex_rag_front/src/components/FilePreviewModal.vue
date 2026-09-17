<!-- Original document preview by Guo Lijian; extended for enterprise media and source locations. -->
<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-3 md:p-6" @click.self="close">
    <section ref="dialog" role="dialog" aria-modal="true" aria-labelledby="preview-title" tabindex="-1" class="bg-white w-full max-w-6xl h-[90vh] rounded-xl shadow-2xl flex flex-col overflow-hidden" @keydown.esc="close" @keydown.tab="trapFocus">
      <header class="border-b px-4 md:px-6 py-3 bg-white shrink-0 flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0 flex-1">
          <h3 id="preview-title" class="font-semibold text-slate-800 truncate">{{ fileName }}</h3>
          <p v-if="locationLabel" class="text-xs text-blue-600 mt-1">{{ t('引用位置：{location}', { location: locationLabel }) }}<span v-if="fileType === 'video'"> · {{ t('已定位，可手动播放') }}</span></p>
        </div>
        <a v-if="fileUrl" :href="fileUrl" :download="fileName" class="text-sm text-blue-600 hover:underline">{{ t('下载原文件') }}</a>
        <button @click="close" :aria-label="t('关闭预览')" class="p-2 text-slate-500 hover:bg-slate-100 rounded-lg"><X class="w-5 h-5" /></button>
      </header>
      <div v-if="fileType === 'pdf' && pageCount" class="flex items-center justify-center gap-4 px-4 py-2 border-b text-sm bg-slate-50">
        <button @click="currentPage--" :disabled="currentPage <= 1" class="text-blue-600 disabled:text-slate-300">{{ t('上一页') }}</button>
        <label>{{ t('页码') }} <input v-model.number="currentPage" type="number" :min="1" :max="pageCount" :aria-label="t('PDF 页码')" class="w-16 py-1 border rounded text-center" @change="clampPage" /> {{ t('共 {count} 页', { count: pageCount }) }}</label>
        <button @click="currentPage++" :disabled="currentPage >= pageCount" class="text-blue-600 disabled:text-slate-300">{{ t('下一页') }}</button>
      </div>
      <main ref="scrollContainer" class="flex-1 overflow-auto bg-slate-100 p-3 md:p-5 relative min-h-0">
        <div v-if="loading" class="flex h-full flex-col items-center justify-center text-slate-500 gap-3"><Loader2 class="w-8 h-8 animate-spin" /><p class="text-sm">{{ t('正在加载原文件…') }}</p><p v-if="mediaType === 'video'" class="text-xs">{{ t('较大的视频需要先加载，再播放和定位。') }}</p></div>
        <div v-else-if="loadError" role="alert" class="flex h-full flex-col items-center justify-center gap-3 text-center"><FileWarning class="w-10 h-10 text-amber-500" /><p class="text-sm text-slate-700">{{ assetMessage(loadError) }}</p><button @click="loadFile" class="text-sm text-blue-600 underline">{{ t('重新加载') }}</button></div>
        <div v-else-if="fileType === 'pdf'" class="mx-auto max-w-4xl bg-white shadow-sm">
          <VuePdfEmbed :source="fileUrl" :page="currentPage" :text-layer="true" @loaded="onPdfLoaded" @rendered="onPdfRendered" @loading-failed="onPdfError" @rendering-failed="onPdfError" class="pdf-container" />
        </div>
        <div v-else-if="fileType === 'text'" class="bg-white p-5 md:p-10 min-h-full max-w-4xl mx-auto shadow-sm text-slate-800 leading-7 whitespace-pre-wrap break-words" v-html="highlightedHtml" />
        <div v-else-if="fileType === 'image'" class="flex items-center justify-center min-h-full"><img :src="fileUrl" :alt="fileName" class="max-w-full max-h-[70vh] object-contain rounded shadow-sm" @error="loadError = '图片无法显示，可下载原文件查看。'" /></div>
        <div v-else-if="fileType === 'video'" class="flex flex-col items-center justify-center min-h-full gap-3">
          <video ref="videoElement" :src="fileUrl" controls playsinline preload="metadata" class="max-w-full max-h-[62vh] w-full bg-black rounded-lg" @loadedmetadata="seekVideo" @error="videoError = true" />
          <p v-if="videoError" class="text-sm text-amber-800">{{ t('浏览器无法播放此视频编码，请下载原文件查看。') }}</p>
          <button v-if="startSeconds !== null && startSeconds !== undefined && !videoError" @click="seekVideo" class="text-sm text-blue-600 underline">{{ t('回到引用时间 {time}', { time: formatTime(startSeconds) }) }}</button>
        </div>
        <div v-else class="flex flex-col items-center justify-center h-full text-center gap-3 text-slate-500"><FileQuestion class="w-12 h-12 text-slate-400" /><p>{{ t('此格式暂不支持直接预览，请下载原文件查看。') }}</p></div>
      </main>
      <details v-if="highlightText" class="shrink-0 border-t bg-white px-5 py-3 max-h-36 overflow-auto text-sm text-slate-600">
        <summary class="cursor-pointer font-medium text-slate-700">{{ t('查看检索到的内容片段') }}</summary>
        <p class="mt-2 leading-6 whitespace-pre-wrap break-words">{{ highlightText }}</p>
      </details>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { X, Loader2, FileQuestion, FileWarning } from 'lucide-vue-next'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import { formatTime, sourceLocation, highlightExcerpt, assetMessage } from '../utils/media'
import { useI18n } from '../i18n'

const { t } = useI18n()

const props = defineProps({
  isOpen: Boolean,
  fileName: String,
  highlightText: String,
  userToken: String,
  docWorkspaceId: [String, Number],
  documentId: [String, Number],
  mediaType: String,
  startSeconds: { type: [Number, String], default: null },
  endSeconds: { type: [Number, String], default: null },
  page: { type: [Number, String], default: null },
})
const emit = defineEmits(['close'])
const dialog = ref(null)
const scrollContainer = ref(null)
const videoElement = ref(null)
const fileUrl = ref('')
const fileType = ref('')
const textContent = ref('')
const loading = ref(false)
const loadError = ref('')
const videoError = ref(false)
const currentPage = ref(1)
const pageCount = ref(0)
let controller
let previousFocus
const locationLabel = computed(() => sourceLocation({ start_seconds: props.startSeconds, end_seconds: props.endSeconds, page: props.page }))
const highlightedHtml = computed(() => highlightExcerpt(textContent.value, props.highlightText))

const cleanup = () => {
  controller?.abort()
  videoElement.value?.pause()
  if (fileUrl.value) URL.revokeObjectURL(fileUrl.value)
  fileUrl.value = ''
  fileType.value = ''
  textContent.value = ''
  loadError.value = ''
  videoError.value = false
  pageCount.value = 0
  loading.value = false
}
const close = () => emit('close')
const clampPage = () => { currentPage.value = Math.max(1, Math.min(pageCount.value || 1, Number(currentPage.value) || 1)) }
const seekVideo = () => {
  const video = videoElement.value
  if (!video || props.startSeconds === null || props.startSeconds === undefined) return
  const duration = Number.isFinite(video.duration) ? video.duration : Number.MAX_SAFE_INTEGER
  video.currentTime = Math.min(Math.max(0, Number(props.startSeconds) || 0), Math.max(0, duration - 0.05))
}
const trapFocus = event => {
  const focusable = [...dialog.value.querySelectorAll('button:not([disabled]), a[href], input, video[controls], summary')]
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first) { event.preventDefault(); return }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}

const loadFile = async () => {
  cleanup()
  const activeController = new AbortController()
  controller = activeController
  loading.value = true
  currentPage.value = Math.max(1, Number(props.page) || 1)
  try {
    const url = props.documentId
      ? `/api/files/assets/${encodeURIComponent(props.documentId)}`
      : `/api/files/${encodeURIComponent(props.fileName)}?doc_workspace_id=${encodeURIComponent(props.docWorkspaceId || 'global')}`
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${props.userToken}` }, signal: activeController.signal,
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => null)
      const key = typeof detail?.detail === 'string' ? detail.detail : '无法加载文件（HTTP {status}）'
      throw Object.assign(new Error(key), { translation: { key, values: { status: response.status } } })
    }
    const contentType = response.headers.get('content-type') || ''
    let blob
    let type = 'unknown'
    let text = ''
    if (contentType.includes('application/json')) {
      const data = await response.json()
      if (data.type !== 'text' || typeof data.content !== 'string') throw new Error('返回的预览格式无法识别。')
      text = data.content
      blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
      type = 'text'
    } else {
      blob = await response.blob()
      const extension = String(props.fileName || '').split('.').pop().toLowerCase()
      if (contentType.includes('application/pdf') || extension === 'pdf') type = 'pdf'
      else if (contentType.startsWith('image/') || ['jpg', 'jpeg', 'png', 'webp'].includes(extension)) type = 'image'
      else if (contentType.startsWith('video/') || ['mp4', 'mov', 'webm', 'mkv'].includes(extension)) type = 'video'
      else if (contentType.startsWith('text/') || ['txt', 'md', 'csv'].includes(extension)) { type = 'text'; text = await blob.text() }
    }
    if (activeController.signal.aborted || !props.isOpen) return
    fileUrl.value = URL.createObjectURL(blob)
    fileType.value = type
    textContent.value = text
    loading.value = false
    await nextTick()
    scrollContainer.value?.querySelector('#txt-mark')?.scrollIntoView({ block: 'center' })
  } catch (error) {
    if (controller === activeController && error.name !== 'AbortError') loadError.value = error.translation || error.message
  } finally {
    if (controller === activeController) loading.value = false
  }
}

const onPdfLoaded = pdf => { pageCount.value = pdf.numPages; clampPage() }
const onPdfError = () => { loadError.value = 'PDF 无法预览，请下载原文件查看。' }
const onPdfRendered = () => {
  if (!props.highlightText) return
  const clean = value => value.replace(/\s/g, '').toLowerCase()
  const needle = clean(props.highlightText)
  for (const span of scrollContainer.value?.querySelectorAll('.textLayer span') || []) {
    const text = clean(span.textContent || '')
    if (text.length > 4 && needle.includes(text)) {
      span.style.backgroundColor = 'rgba(250, 204, 21, 0.4)'
    }
  }
}

watch(() => [props.isOpen, props.documentId, props.fileName, props.docWorkspaceId, props.userToken], async ([open], previous) => {
  if (!open) {
    cleanup()
    previousFocus?.focus?.()
    return
  }
  if (!previous?.[0]) previousFocus = document.activeElement
  await nextTick()
  dialog.value?.focus()
  if (props.fileName || props.documentId) loadFile()
}, { immediate: true })
watch(() => props.startSeconds, () => seekVideo())
watch(() => props.page, () => { currentPage.value = Math.max(1, Number(props.page) || 1); if (pageCount.value) clampPage() })
onBeforeUnmount(cleanup)
</script>

<style>
.pdf-container { position: relative; }
.pdf-container .textLayer { position: absolute; inset: 0; overflow: hidden; line-height: 1; transform-origin: 0 0; }
.pdf-container .textLayer span { position: absolute; color: transparent; white-space: pre; cursor: text; transform-origin: 0 0; line-height: 1; margin: 0; padding: 0; border: none; }
.pdf-container .textLayer ::selection { background: rgba(59, 130, 246, 0.3); }
</style>
