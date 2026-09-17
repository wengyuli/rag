<template>
  <div class="overflow-x-auto rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500" tabindex="0" role="region" :aria-label="t('架构图可横向滚动')">
    <svg ref="svgElement" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1160 620" class="block w-full min-w-[900px]" role="img" :aria-labelledby="`${uid}-title ${uid}-desc`" font-family="Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif">
      <title :id="`${uid}-title`">{{ t(technical ? '技术架构图' : '产品流程图') }}</title>
      <desc :id="`${uid}-desc`">{{ t(technical ? 'Vue 与 Nginx、FastAPI 与 LlamaIndex、Ollama、PostgreSQL 与 pgvector 组成四个本地 Docker 服务，使用本地文件与模型卷。' : '资料从上传到本地解析、建立检索知识库，经 AI 查询生成附带原文引用的回答。') }}</desc>
      <defs>
        <marker :id="`${uid}-arrow`" markerWidth="8" markerHeight="8" refX="6.5" refY="4" orient="auto-start-reverse"><path d="M1 1 L7 4 L1 7" fill="none" stroke="#64748b" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" /></marker>
        <marker :id="`${uid}-blue`" markerWidth="8" markerHeight="8" refX="6.5" refY="4" orient="auto-start-reverse"><path d="M1 1 L7 4 L1 7" fill="none" stroke="#2563eb" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" /></marker>
      </defs>
      <rect width="1160" height="620" rx="20" fill="#f8fafc" />
      <text x="32" y="39" font-size="21" font-weight="700" fill="#0f172a">{{ t(technical ? '本地 Docker 部署' : '从资料到知识，从问题到答案') }}</text>
      <text x="32" y="65" font-size="13" fill="#64748b">{{ t(technical ? '四个服务协同，模型与企业资料持久化保存' : '资料内容在本地解析、存储与检索') }}</text>

      <template v-if="!technical">
        <rect x="16" y="90" width="1128" height="482" rx="22" fill="#f1f5f9" stroke="#cbd5e1" stroke-dasharray="5 5" />
        <text x="38" y="119" font-size="12" font-weight="700" fill="#64748b">{{ t('企业本地环境') }}</text>
        <g v-for="x in [216, 444, 672, 900]" :key="x"><path :d="`M ${x} 312 H ${x + 34}`" fill="none" stroke="#64748b" stroke-width="1.8" :marker-end="arrow" /></g>
        <rect x="716" y="121" width="184" height="46" rx="12" fill="#eff6ff" stroke="#93c5fd" />
        <text x="808" y="149" text-anchor="middle" font-size="13" font-weight="600" fill="#1d4ed8">{{ t('自然语言提问') }}</text>
        <path d="M808 167 V189" fill="none" stroke="#2563eb" stroke-width="1.8" :marker-end="blueArrow" />
        <path d="M124 428 V501 H250" fill="none" stroke="#94a3b8" stroke-width="1.6" :marker-end="arrow" />
        <path d="M580 428 V462" fill="none" stroke="#94a3b8" stroke-width="1.6" :marker-end="arrow" />
        <path d="M1036 428 V501 H724" fill="none" stroke="#2563eb" stroke-width="1.6" stroke-dasharray="5 4" :marker-end="blueArrow" />
        <text x="898" y="489" text-anchor="middle" font-size="12" fill="#2563eb">{{ t('回到原始资料核对') }}</text>
        <rect x="260" y="472" width="456" height="70" rx="12" fill="#ffffff" stroke="#cbd5e1" />
        <text x="282" y="495" font-size="14" font-weight="600" fill="#334155">{{ t('原文件与定位信息') }}</text>
        <text v-for="(line,index) in wrap(t('文件、页码与时间点贯穿解析、检索和预览'), 412, 12)" :key="line" x="282" :y="515 + index * 16" font-size="12" fill="#64748b">{{ line }}</text>
        <text x="580" y="599" text-anchor="middle" font-size="12" fill="#64748b">{{ t('管理员全库 · 成员本部门与公共资料') }}</text>
      </template>

      <template v-else>
        <rect x="16" y="90" width="1128" height="444" rx="22" fill="#eff6ff" stroke="#bfdbfe" stroke-dasharray="5 5" />
        <path d="M272 213 H316" fill="none" stroke="#64748b" stroke-width="1.8" :marker-start="arrow" :marker-end="arrow" />
        <path d="M650 211 H736" fill="none" stroke="#2563eb" stroke-width="1.8" :marker-start="blueArrow" :marker-end="blueArrow" />
        <text x="697" y="191" text-anchor="middle" font-size="11" fill="#2563eb">{{ t('本地推理') }}</text>
        <path d="M488 322 V365" fill="none" stroke="#64748b" stroke-width="1.8" :marker-start="arrow" :marker-end="arrow" />
        <path d="M650 288 H696 V352 H922 V386" fill="none" stroke="#64748b" stroke-width="1.8" :marker-end="arrow" />
        <text x="823" y="344" text-anchor="middle" font-size="11" fill="#64748b">{{ t('原件与缓存') }}</text>
        <rect x="32" y="552" width="1096" height="50" rx="12" fill="#e2e8f0" />
        <text x="48" y="572" font-size="11" font-weight="700" fill="#475569">{{ t('查询链路') }}</text>
        <text x="48" y="592" font-size="12" fill="#334155">{{ t('鉴权 → 问题向量化 → 按范围召回 → 权限复核 → 重排 → 回答与引用') }}</text>
      </template>

      <g v-for="node in nodes" :key="node.id">
        <rect :x="node.x" :y="node.y" :width="node.w" :height="node.h" rx="16" fill="#fff" stroke="#dbe3ee" />
        <rect :x="node.x" :y="node.y" :width="node.w" height="5" rx="2.5" :fill="node.color" />
        <text :x="node.x + 16" :y="node.y + 27" font-size="10.5" font-weight="700" letter-spacing="0.5" :fill="node.color">{{ node.id }} / {{ t(node.kicker) }}</text>
        <text v-for="(line,index) in wrap(t(node.title), node.w - 32, 17)" :key="`title-${index}`" :x="node.x + 16" :y="node.y + 54 + index * 21" font-size="17" font-weight="700" fill="#0f172a">{{ line }}</text>
        <text v-for="(line,index) in bodyLines(node)" :key="`body-${index}`" :x="node.x + 16" :y="node.y + node.bodyY + index * 18" font-size="12.5" fill="#475569">{{ line }}</text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import { useI18n } from '../i18n'
const props = defineProps({ mode: { type: String, default: 'product' } })
const { t, locale } = useI18n()
const svgElement = ref(null)
const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
const technical = computed(() => props.mode === 'technical')
const arrow = `url(#${uid}-arrow)`
const blueArrow = `url(#${uid}-blue)`

// Word-aware SVG text wrapping keeps exported diagrams independent of HTML/CSS.
function wrap(value, width, fontSize) {
  const tokens = String(value).match(/[\u3400-\u9fff]|[^\s\u3400-\u9fff]+|\s+/g) || []
  const limit = width / fontSize
  const weight = text => [...text].reduce((sum, char) => sum + (/[\u3400-\u9fff]/.test(char) ? 1 : /[MW@]/.test(char) ? 0.82 : /[ilI.,:;!' ]/.test(char) ? 0.3 : 0.56), 0)
  const lines = []
  let line = ''
  for (const token of tokens) {
    if (line && weight(line + token) > limit) { lines.push(line.trim()); line = token.trimStart() }
    else line += token
  }
  if (line.trim()) lines.push(line.trim())
  return lines
}
const bodyLines = node => node.items.flatMap(item => wrap(t(item), node.w - 32, 12.5))
const nodes = computed(() => technical.value ? [
  {id:'01',x:48,y:150,w:224,h:172,bodyY:99,color:'#2563eb',kicker:'网页服务',title:'Vue 3 · Nginx',items:['文件管理与 AI 查询','中英文界面与资源监控']},
  {id:'02',x:326,y:130,w:324,h:192,bodyY:112,color:'#0891b2',kicker:'应用服务',title:'FastAPI · LlamaIndex',items:['鉴权、任务队列与文档提取','FFmpeg · Whisper · BGE 重排','检索编排与流式回答']},
  {id:'03',x:746,y:130,w:366,h:192,bodyY:100,color:'#7c3aed',kicker:'模型服务',title:'Ollama',items:['Qwen2.5 · 回答生成','Qwen3-VL · 视觉理解','BGE-M3 · 文本向量化']},
  {id:'04',x:326,y:375,w:324,h:139,bodyY:86,color:'#2563eb',kicker:'数据库服务',title:'PostgreSQL 16 + pgvector',items:['文本片段、向量与来源信息','账号、部门、任务与会话']},
  {id:'+',x:746,y:396,w:366,h:118,bodyY:79,color:'#059669',kicker:'持久化存储',title:'本地文件与模型',items:['原件、缩略图与解析缓存','模型权重保存在本地卷']},
] : [
  {id:'01',x:32,y:198,w:184,h:230,bodyY:100,color:'#2563eb',kicker:'多媒体资料',title:'统一上传',items:['文档 · PDF / Office','图片 · 封面 / 截图','视频 · 培训 / 操作']},
  {id:'02',x:260,y:198,w:184,h:230,bodyY:100,color:'#0891b2',kicker:'内容理解',title:'AI 解析',items:['文档提取与扫描页识别','图片描述与文字识别','视频抽帧与语音转写']},
  {id:'03',x:488,y:198,w:184,h:230,bodyY:100,color:'#7c3aed',kicker:'知识组织',title:'检索知识库',items:['文本切块与向量化','保留文件与定位信息','建立语义检索索引']},
  {id:'04',x:716,y:198,w:184,h:230,bodyY:100,color:'#2563eb',kicker:'按权限查询',title:'AI 查询',items:['范围过滤与向量召回','可见性复核与重排','结合资料生成回答']},
  {id:'05',x:944,y:198,w:184,h:230,bodyY:100,color:'#059669',kicker:'结果可核对',title:'答案与引用',items:['查看相关资料片段','打开原文与图片','定位视频时间点']},
])

function download() {
  if (!svgElement.value) return
  const svg = svgElement.value.cloneNode(true)
  svg.setAttribute('width', '1160')
  svg.setAttribute('height', '620')
  svg.removeAttribute('class')
  const content = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg)
  const blob = new Blob([content], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `enterprise-assets-${technical.value ? 'technical' : 'product'}-${locale.value}.svg`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
defineExpose({ download })
</script>
