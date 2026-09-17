<!--
  AI 查询聊天组件

  提供与AI助手的实时对话界面，支持流式文本显示
  包含消息历史、文件引用展示、打字机效果等功能

  @author Guo Lijian
  @version 1.0.0
  @since 2025-12-06
-->
<template>
  <div class="flex flex-col h-full bg-slate-50">
    <header class="h-16 bg-white border-b flex items-center justify-between px-6 shadow-sm shrink-0">
      <h2 class="text-lg font-semibold text-slate-800 flex items-center gap-2">
        <MessageSquare class="w-5 h-5 text-blue-600" />
        <!-- 加个 ?. 防止报错 -->
        {{ displayWorkspace(currentWorkspace?.name, currentWorkspace?.id) }} · {{ t('内容助手') }}
      </h2>
    </header>

    <div class="flex-1 overflow-y-auto p-6 space-y-6" ref="messagesContainer">
      <div v-for="(msg, idx) in messages" :key="idx"
        :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']">
        <div
          :class="['max-w-2xl p-4 rounded-lg shadow-sm', msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white text-slate-800 border']">
          <div v-if="msg.content" class="relative group mb-2">
             <div 
               class="leading-relaxed prose prose-sm max-w-none select-text cursor-text" 
               :class="msg.role === 'user' ? 'prose-invert' : ''"
               v-html="md.render(messageText(msg) || '')"
             ></div>
            <button 
              v-if="msg.role === 'assistant'"
              @click="copyToClipboard(messageText(msg), idx)"
              class="absolute -bottom-6 right-0 p-1.5 text-slate-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs"
              :title="t('复制内容')" :aria-label="t('复制内容')"
            >
              <Check v-if="copiedIndex === idx" class="w-3.5 h-3.5 text-green-500" />
              <Copy v-else class="w-3.5 h-3.5" />
              <span v-if="copiedIndex === idx" class="text-green-500">{{ t('已复制') }}</span>
              <span v-else>{{ t('复制') }}</span>
            </button>
          </div>
          <!-- 即使 sources 出来了，这里依然在转圈，用户就知道还没完 -->
          <div v-if="msg.thinking" class="flex items-center gap-2 text-slate-400 text-sm py-1">
            <Loader2 class="w-4 h-4 animate-spin" />
            <span>{{ msg.content ? t('正在生成...') : t('深度检索中...') }}</span>
          </div>
          <div v-if="msg.role === 'assistant' && msg.sources && !msg.thinking" class="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
            <p class="font-semibold mb-1 text-slate-700">{{ t('引用来源：') }}</p>
            <div v-if="msg.sources.length > 0" class="space-y-1">
              <button
                v-for="(s, i) in msg.sources" :key="i"
                @click="openPreview(s)"
                class="flex w-full text-left items-center gap-2 p-2 rounded hover:bg-slate-100 transition group/file">
                <component 
                  :is="getFileIcon(s.file_name || s).icon" 
                  :class="['w-4 h-4', getFileIcon(s.file_name || s).color]" 
                />
                <!-- 如果 s 是对象显示 s.file_name，如果是字符串显示 s -->
                <span class="hover:underline break-all">{{ s.file_name || s }}</span>
                <span v-if="sourceLocation(s)" class="text-blue-600 whitespace-nowrap ml-auto">{{ sourceLocation(s) }}</span>
                <span v-if="s.source_kind === 'audio'" class="text-slate-400 shrink-0">{{ t('语音') }}</span>
                <span v-else-if="s.source_kind === 'visual'" class="text-slate-400 shrink-0">{{ t('画面') }}</span>
              </button>
            </div>
            <div v-else class="text-slate-400 italic flex items-center gap-1">
              <span class="w-3 h-3 inline-block"></span>
              {{ t('无相关资料') }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="p-4 bg-white border-t shrink-0">
      <div class="max-w-4xl mx-auto relative">
        <input v-model="input" @keydown.enter="handleSend" type="text" :placeholder="t('例如：封面怎么选？拍摄前准备什么？发布流程是什么？')" :aria-label="t('向企业数字资产 AI 管理平台助手提问')"
          class="w-full p-4 pr-12 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm select-text"
          :disabled="isLoading" />
        <button @click="handleSend" :disabled="isLoading || !input.trim()" :aria-label="t('发送问题')"
          class="absolute right-3 top-3 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>
    <FilePreviewModal 
      :is-open="isPreviewOpen"
      :file-name="previewFileName"
      :highlight-text="previewHighlight"
      :user-token="user.token"
      :doc-workspace-id="docWorkspaceId"
      :document-id="previewSource.document_id"
      :media-type="previewSource.media_type"
      :start-seconds="previewSource.start_seconds"
      :end-seconds="previewSource.end_seconds"
      :page="previewSource.page"
      @close="isPreviewOpen = false"
    />
  </div>
</template>

<script setup>
// 🔥🔥🔥 修正点：补全 onMounted
import { ref, watch, nextTick, onMounted } from 'vue' 
import { 
  MessageSquare, Send, FileText, Loader2, Copy, Check,
  FileSpreadsheet, FileCode, File, FileImage, FileVideo
 } from 'lucide-vue-next'
import { useChat } from '../composables/useChat'
import { useWorkspace } from '../composables/useWorkspace'
import MarkdownIt from 'markdown-it'
import FilePreviewModal from '../components/FilePreviewModal.vue'
import { useAuth } from '../composables/useAuth'
import { sourceLocation } from '../utils/media'
import { useI18n } from '../i18n'

const { t, displayWorkspace } = useI18n()

const isPreviewOpen = ref(false)
const previewFileName = ref('')
const previewHighlight = ref('')
const docWorkspaceId = ref('')
const previewSource = ref({})
const { user } = useAuth()

const md = new MarkdownIt()
const { messages, sendMessage, isLoading } = useChat()
const { currentWorkspace } = useWorkspace()

const input = ref('')
const messagesContainer = ref(null)
const copiedIndex = ref(-1)

// Translate only the local welcome message; user and server content stays intact.
const messageText = message => message.isLocalWelcome ? t(message.content) : message.content

const handleSend = () => {
  if (!input.value.trim() || isLoading.value) return
  sendMessage(input.value)
  input.value = ''
}

const openPreview = source => {
  const citation = typeof source === 'string' ? { file_name: source } : source
  previewFileName.value = citation.file_name || ''
  previewHighlight.value = citation.text_chunk || ''
  docWorkspaceId.value = citation.workspace_id || ''
  previewSource.value = citation
  isPreviewOpen.value = true
}

const copyToClipboard = async (text, idx) => {
  try {
    await navigator.clipboard.writeText(text)
    copiedIndex.value = idx
    setTimeout(() => { copiedIndex.value = -1 }, 2000)
  } catch (err) {
    console.error('复制失败', err)
  }
}

const scrollToBottom = async (smooth = true) => {
  await nextTick()
  if (messagesContainer.value) {
    const el = messagesContainer.value
    
    // 关键修改：初始化时使用 scrollTop 直接赋值，比 scrollTo 更可靠
    if (smooth) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      el.scrollTop = el.scrollHeight
    }
  }
}

const getFileIcon = (filename) => {
  if (!filename) return { icon: File, color: 'text-slate-400' }
  
  const ext = filename.split('.').pop().toLowerCase()

  switch (ext) {
    case 'pdf':
      return { icon: FileText, color: 'text-red-500' } // PDF 用红色
    case 'doc':
    case 'docx':
      return { icon: FileText, color: 'text-blue-500' } // Word 用蓝色
    case 'xls':
    case 'xlsx':
    case 'csv':
      return { icon: FileSpreadsheet, color: 'text-green-600' } // Excel 用绿色
    case 'ppt':
    case 'pptx':
      return { icon: File, color: 'text-orange-500' } // PPT 用橙色
    case 'txt':
    case 'md':
    case 'json':
    case 'py':
      return { icon: FileCode, color: 'text-slate-600' } // 代码/文本用深灰
    case 'jpg':
    case 'png':
    case 'jpeg':
    case 'webp':
      return { icon: FileImage, color: 'text-purple-500' } // 图片用紫色
    case 'mp4':
    case 'mov':
    case 'webm':
    case 'mkv':
      return { icon: FileVideo, color: 'text-amber-600' }
    default:
      return { icon: File, color: 'text-slate-400' } // 未知格式
  }
}

// 监听消息变化 (保持平滑滚动)
watch(messages, () => {
  scrollToBottom(true)
}, { deep: true })

// 组件挂载/切换回来时 (强制滚动到底部)
onMounted(async () => {
  // 1. 立即尝试一次
  await scrollToBottom(false)
  
  // 2. 延迟执行：给浏览器一点时间完成布局渲染 (Markdown渲染、CSS加载等)
  // 如果 100ms 还是不行，可以尝试改成 300ms，通常 100-200ms 足够
  setTimeout(() => {
    scrollToBottom(false)
  }, 200)
})
</script>