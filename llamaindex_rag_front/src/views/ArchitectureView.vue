<template>
  <div :class="[standalone ? 'min-h-screen' : 'h-full overflow-y-auto', 'bg-slate-50 text-slate-800']">
    <header v-if="standalone" class="border-b border-slate-200 bg-white">
      <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4 md:px-8">
        <router-link to="/" class="flex min-w-0 items-center gap-3 text-sm font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white"><LibraryBig class="h-5 w-5" aria-hidden="true" /></span>
          <span class="max-w-64 leading-snug">{{ t('企业数字资产 AI 管理平台') }}</span>
        </router-link>
        <div class="flex flex-wrap items-center gap-4">
          <LanguageSwitcher />
          <router-link to="/" class="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
            <ArrowLeft class="h-4 w-4" aria-hidden="true" />{{ t('返回系统') }}
          </router-link>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-6xl space-y-7 px-4 py-7 md:space-y-9 md:px-8 md:py-10">
      <section class="relative overflow-hidden rounded-2xl border border-blue-100 bg-white p-6 md:p-9" aria-labelledby="architecture-title">
        <div class="pointer-events-none absolute right-0 top-0 h-56 w-56 rounded-full bg-blue-50 blur-3xl" aria-hidden="true" />
        <div class="relative max-w-4xl">
          <p class="mb-4 inline-flex items-center gap-2 text-xs font-semibold tracking-wide text-blue-600">
            <Layers3 class="h-4 w-4" aria-hidden="true" />{{ t('文档 · 图片 · 视频') }}
          </p>
          <h1 id="architecture-title" class="max-w-3xl text-3xl font-bold leading-tight tracking-tight text-slate-900 md:text-4xl md:leading-tight">{{ t('让企业资料，成为可查询的知识') }}</h1>
          <p class="mt-4 max-w-3xl text-sm leading-7 text-slate-500 md:text-base">{{ t('让文档、图片和视频进入同一个资料库，通过 AI 查询找到线索，并回到原始内容核对。') }}</p>
          <div class="mt-6 flex flex-wrap gap-x-6 gap-y-3 text-xs font-medium text-slate-600 md:text-sm">
            <span class="inline-flex items-center gap-2"><FolderOpen class="h-4 w-4 text-blue-600" aria-hidden="true" />{{ t('统一内容管理') }}</span>
            <span class="inline-flex items-center gap-2"><Link2 class="h-4 w-4 text-blue-600" aria-hidden="true" />{{ t('可追溯的回答') }}</span>
            <span class="inline-flex items-center gap-2"><Server class="h-4 w-4 text-blue-600" aria-hidden="true" />{{ t('本地模型运行') }}</span>
          </div>
        </div>
      </section>

      <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white" aria-labelledby="diagram-heading">
        <div class="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 px-5 py-5 md:px-7">
          <div>
            <h2 id="diagram-heading" class="text-lg font-semibold text-slate-900">{{ t('系统如何组织知识') }}</h2>
            <p class="mt-1 text-xs leading-5 text-slate-500">{{ t(diagramMode === 'product' ? '从资料入库，到答案引用。' : '查看解析、索引与检索之间的数据流。') }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <router-link v-if="!standalone" to="/architecture" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-xs font-medium text-slate-500 hover:bg-slate-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
              <ExternalLink class="h-4 w-4" aria-hidden="true" />{{ t('独立展示') }}
            </router-link>
            <button type="button" @click="downloadDiagram" :disabled="exporting" class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
              <Loader2 v-if="exporting" class="h-4 w-4 animate-spin" aria-hidden="true" /><Download v-else class="h-4 w-4" aria-hidden="true" />
              {{ t(exporting ? '正在导出…' : '下载架构图') }}
            </button>
          </div>
        </div>
        <div class="px-5 pt-5 md:px-7">
          <div class="inline-flex max-w-full flex-wrap gap-1 rounded-xl bg-slate-100 p-1" role="group" :aria-label="t('架构图视图')">
            <button type="button" @click="diagramMode = 'product'" :aria-pressed="diagramMode === 'product'" :class="['inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 md:text-sm', diagramMode === 'product' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-800']">
              <Workflow class="h-4 w-4" aria-hidden="true" />{{ t('产品流程') }}
            </button>
            <button type="button" @click="diagramMode = 'technical'" :aria-pressed="diagramMode === 'technical'" :class="['inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 md:text-sm', diagramMode === 'technical' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-800']">
              <Network class="h-4 w-4" aria-hidden="true" />{{ t('技术架构') }}
            </button>
          </div>
          <p v-if="exportError" role="alert" class="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{{ t('图示暂时无法导出，请稍后重试。') }}</p>
        </div>
        <div class="px-2 pb-4 pt-2 md:px-5 md:pb-6">
          <ArchitectureDiagram ref="diagram" :mode="diagramMode" />
        </div>
      </section>

      <section aria-labelledby="use-cases-heading">
        <div class="mb-4 flex items-center gap-3">
          <h2 id="use-cases-heading" class="text-base font-semibold text-slate-800">{{ t('把资料用在日常工作里') }}</h2>
          <div class="h-px flex-1 bg-slate-200" aria-hidden="true" />
        </div>
        <div class="grid gap-4 md:grid-cols-3">
          <article v-for="item in useCases" :key="item.title" class="rounded-xl border border-slate-200 bg-white p-5">
            <div class="mb-4 inline-flex rounded-lg bg-slate-50 p-2.5 text-blue-600"><component :is="item.icon" class="h-5 w-5" aria-hidden="true" /></div>
            <h3 class="text-sm font-semibold text-slate-800">{{ t(item.title) }}</h3>
            <p class="mt-2 text-xs leading-6 text-slate-500">{{ t(item.description) }}</p>
          </article>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-slate-100/60 px-5 py-5 md:px-6" aria-labelledby="scope-heading">
        <h2 id="scope-heading" class="text-sm font-semibold text-slate-700">{{ t('部署与使用范围') }}</h2>
        <div class="mt-4 grid gap-5 text-xs leading-6 text-slate-500 md:grid-cols-3">
          <div>
            <h3 class="mb-1 font-medium text-slate-700">{{ t('模型就绪后，本地解析与查询') }}</h3>
            <p>{{ t('首次部署需下载模型。模型准备完成后，资料解析、索引和查询在本地服务中运行。') }}</p>
          </div>
          <div>
            <h3 class="mb-1 font-medium text-slate-700">{{ t('公共资料与部门资料') }}</h3>
            <p>{{ t('公共资料供全员使用；部门资料按所属部门管理与检索，管理员可管理全部资料。') }}</p>
          </div>
          <div>
            <h3 class="mb-1 font-medium text-slate-700">{{ t('视频处理边界') }}</h3>
            <p>{{ t('视频结合抽帧分析与语音转写，可能遗漏短暂画面。当前单文件最多 128 MB，视频最长 5 分钟。') }}</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowLeft, Clapperboard, Download, ExternalLink, FolderArchive, FolderOpen, GraduationCap, Layers3, LibraryBig, Link2, Loader2, Network, Server, Workflow } from 'lucide-vue-next'
import ArchitectureDiagram from '../components/ArchitectureDiagram.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { useI18n } from '../i18n'

defineProps({ standalone: { type: Boolean, default: false } })
const { t } = useI18n()
const diagramMode = ref('product')
const diagram = ref(null)
const exporting = ref(false)
const exportError = ref(false)
// Keep source keys here so switching languages also updates these cards.
const useCases = [
  { icon: FolderArchive, title: '资料归档', description: '按文件名与媒体类型集中查找文档、图片和视频，让项目资料随时可用。' },
  { icon: GraduationCap, title: '培训复用', description: '从操作文档和培训视频查找步骤，并回到相关页面或视频时间点核对。' },
  { icon: Clapperboard, title: '内容生产', description: '查询策划方案、封面规范和拍摄素材，为选题与创作整理参考。' },
]
async function downloadDiagram() {
  if (exporting.value) return
  exporting.value = true
  exportError.value = false
  try {
    if (typeof diagram.value?.download !== 'function') throw new Error('Diagram export is not ready')
    await diagram.value.download()
  } catch {
    exportError.value = true
  } finally {
    exporting.value = false
  }
}
</script>
