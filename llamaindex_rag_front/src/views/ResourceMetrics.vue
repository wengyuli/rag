<template>
  <div class="h-full overflow-y-auto bg-slate-50 p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-slate-800">资源监控</h1>
          <p class="mt-2 text-sm text-slate-500">查看 CPU、内存和资料存储空间的实时使用情况。</p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <button type="button" @click="toggleAutoRefresh" :aria-pressed="autoRefresh"
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
            <Pause v-if="autoRefresh" class="w-4 h-4" /><Play v-else class="w-4 h-4" />
            {{ autoRefresh ? '暂停自动刷新' : '恢复自动刷新' }}
          </button>
          <button type="button" @click="fetchMetrics" :disabled="loading"
            class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2">
            <RefreshCw :class="['w-4 h-4', loading ? 'animate-spin' : '']" />
            {{ loading ? '刷新中' : '立即刷新' }}
          </button>
        </div>
      </header>

      <section class="rounded-xl border border-slate-200 bg-white p-4 md:p-5" aria-label="监控范围与状态">
        <div class="flex flex-wrap justify-between gap-3">
          <div class="flex items-start gap-3">
            <Server class="w-5 h-5 shrink-0 text-blue-600 mt-0.5" />
            <div>
              <p class="text-sm font-semibold text-slate-800">监控范围：{{ metrics?.scope?.label || '等待获取运行环境' }}</p>
              <p class="mt-1 text-sm leading-6 text-slate-500">{{ metrics?.scope?.description || '连接成功后显示 CPU 和内存指标对应的运行环境。' }}</p>
            </div>
          </div>
          <div class="shrink-0 text-xs leading-6 text-slate-500">
            <p class="flex items-center gap-1.5">
              <span :class="['h-2 w-2 rounded-full', error || stale ? 'bg-amber-500' : metrics && autoRefresh ? 'bg-emerald-500' : 'bg-slate-400']" />
              {{ refreshStatus }}
            </p>
            <p>采样时间：<time v-if="metrics?.sampled_at" :datetime="metrics.sampled_at">{{ formatDateTime(metrics.sampled_at) }}</time><span v-else>—</span></p>
          </div>
        </div>
      </section>

      <div v-if="error" role="alert" class="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
        <AlertTriangle class="w-5 h-5 shrink-0 mt-0.5" />
        <p>{{ error }}{{ metrics ? ' 当前保留上次采样数据，请留意采样时间。' : '' }}</p>
      </div>
      <div v-else-if="stale" role="status" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{{ autoRefresh ? '采样数据已过期，正在等待服务器提供最新指标。' : '采样数据已过期；自动刷新已暂停，可点击立即刷新获取最新指标。' }}</div>
      <div v-if="metrics?.errors?.length" role="status" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
        <p class="font-medium">部分指标暂不可用</p>
        <ul class="list-disc pl-5"><li v-for="(message, index) in metrics.errors" :key="index">{{ message }}</li></ul>
      </div>

      <section class="grid grid-cols-1 gap-4 lg:grid-cols-3" aria-label="当前资源使用情况">
        <article v-for="card in cards" :key="card.key" class="rounded-xl border border-slate-200 bg-white p-5 md:p-6">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-sm font-semibold text-slate-700">{{ card.title }}</h2>
            <div :class="['rounded-lg p-2.5', card.iconClasses]"><component :is="card.icon" class="w-5 h-5" /></div>
          </div>
          <p class="mt-4 text-3xl font-bold tabular-nums text-slate-800">{{ percentLabel(card.percent) }}<span v-if="isNumber(card.percent)" class="ml-1 text-lg font-medium text-slate-400">%</span></p>
          <p class="mt-1 min-h-5 text-xs text-slate-500">{{ card.caption }}</p>
          <div class="mt-5 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" :aria-label="card.title" :aria-valuenow="isNumber(card.percent) ? clampPercent(card.percent) : undefined" :aria-valuetext="isNumber(card.percent) ? `${percentLabel(card.percent)}%` : '暂无数据'" aria-valuemin="0" aria-valuemax="100">
            <div :class="['h-full rounded-full transition-[width] duration-500', card.barClass]" :style="{ width: `${clampPercent(card.percent)}%` }" />
          </div>
          <dl class="mt-5 space-y-2 text-sm">
            <div v-for="row in card.rows" :key="row.label" class="flex justify-between gap-3">
              <dt class="text-slate-500">{{ row.label }}</dt><dd class="font-medium tabular-nums text-slate-700 text-right">{{ row.value }}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-5 md:p-6" aria-label="资源使用率历史趋势">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="font-semibold text-slate-800">近 2 分钟使用率</h2>
            <p class="mt-1 text-xs leading-5 text-slate-500">每 {{ intervalSeconds }} 秒采样；无数据的时段显示为空白。</p>
          </div>
          <span class="text-xs text-slate-400">{{ history.length }} 个采样点</span>
        </div>
        <div v-if="history.length" class="mt-5 h-72 md:h-80" role="img" :aria-label="chartDescription">
          <v-chart class="h-full w-full" :option="chartOption" autoresize />
        </div>
        <div v-else class="flex h-72 flex-col items-center justify-center gap-3 text-slate-400">
          <Activity class="w-8 h-8" />
          <p class="text-sm">{{ error ? '连接恢复后显示趋势' : '等待第一组采样数据' }}</p>
        </div>
        <p class="mt-4 border-t border-slate-100 pt-4 text-xs leading-6 text-slate-500">磁盘指标表示资料目录所在文件系统的总容量与占用，包含同一文件系统中的其他数据。</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { Activity, AlertTriangle, Cpu, HardDrive, MemoryStick, Pause, Play, RefreshCw, Server } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'

const { user } = useAuth()
const metrics = ref(null)
const loading = ref(false)
const error = ref('')
const autoRefresh = ref(true)
const clockNow = ref(Date.now())
let active = false
let timer = null
let clockTimer = null
let controller = null

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value)
const clampPercent = (value) => isNumber(value) ? Math.min(100, Math.max(0, value)) : 0
const percentLabel = (value) => isNumber(value) ? value.toFixed(1) : '—'
const intervalSeconds = computed(() => isNumber(metrics.value?.interval_seconds) ? Math.min(30, Math.max(1, metrics.value.interval_seconds)) : 2)
const stale = computed(() => {
  if (!metrics.value?.sampled_at) return false
  const sampled = Date.parse(metrics.value.sampled_at)
  return !Number.isFinite(sampled) || clockNow.value - sampled > Math.max(10_000, intervalSeconds.value * 3_000)
})
const refreshStatus = computed(() => {
  if (!autoRefresh.value) return `自动刷新已暂停${error.value || stale.value ? (metrics.value ? ' · 数据已过期' : ' · 连接异常') : ''}`
  if (error.value || stale.value) return metrics.value ? '数据已过期' : '连接异常'
  if (!metrics.value) return '正在连接'
  return `每 ${intervalSeconds.value} 秒自动刷新`
})

function formatBytes(value) {
  if (!isNumber(value) || value < 0) return '—'
  if (value === 0) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  const power = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)))
  return `${(value / (1024 ** power)).toLocaleString('zh-CN', { maximumFractionDigits: power < 2 ? 0 : 2 })} ${units[power]}`
}
function formatDateTime(value) {
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'
}
function formatClock(value) {
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'
}

const cpuCaption = computed(() => {
  if (isNumber(metrics.value?.cpu?.percent)) return '所有逻辑核心的平均使用率'
  if (metrics.value?.errors?.some((message) => /CPU/i.test(message)) || metrics.value?.scope?.kind === 'process') return 'CPU 指标暂不可用，请查看采样提示'
  return metrics.value ? '首个 CPU 采样周期尚未完成' : '尚未取得 CPU 指标'
})

const cards = computed(() => [
  {
    key: 'cpu', title: 'CPU 使用率', icon: Cpu, iconClasses: 'bg-blue-50 text-blue-600', barClass: 'bg-blue-500', percent: metrics.value?.cpu?.percent,
    caption: cpuCaption.value,
    rows: [
      { label: '逻辑核心', value: isNumber(metrics.value?.cpu?.logical_cores) ? `${metrics.value.cpu.logical_cores} 个` : '—' },
      { label: '统计范围', value: metrics.value?.scope?.label || '—' },
    ],
  },
  {
    key: 'memory', title: '内存使用率', icon: MemoryStick, iconClasses: 'bg-violet-50 text-violet-600', barClass: 'bg-violet-500', percent: metrics.value?.memory?.percent,
    caption: '已用内存 = 总内存 − 可用内存',
    rows: [
      { label: '已用 / 总量', value: `${formatBytes(metrics.value?.memory?.used_bytes)} / ${formatBytes(metrics.value?.memory?.total_bytes)}` },
      { label: '可用内存', value: formatBytes(metrics.value?.memory?.available_bytes) },
      { label: '后端容器（含缓存）', value: formatBytes(metrics.value?.backend?.memory_bytes) },
    ],
  },
  {
    key: 'disk', title: '磁盘使用率', icon: HardDrive, iconClasses: 'bg-amber-50 text-amber-600', barClass: 'bg-amber-500', percent: metrics.value?.disk?.percent,
    caption: metrics.value?.disk?.label || '资料存储卷',
    rows: [
      { label: '已用 / 总容量', value: `${formatBytes(metrics.value?.disk?.used_bytes)} / ${formatBytes(metrics.value?.disk?.total_bytes)}` },
      { label: '可用空间', value: formatBytes(metrics.value?.disk?.free_bytes) },
    ],
  },
])

const history = computed(() => {
  const samples = Array.isArray(metrics.value?.history) ? metrics.value.history : []
  return samples.filter((item) => item && Number.isFinite(Date.parse(item.timestamp))).slice(-60).sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
})
const chartDescription = computed(() => `CPU、内存和磁盘近 2 分钟使用率趋势，纵轴 0% 至 100%。当前 CPU ${percentLabel(metrics.value?.cpu?.percent)}，内存 ${percentLabel(metrics.value?.memory?.percent)}，磁盘 ${percentLabel(metrics.value?.disk?.percent)}。`)
const chartOption = computed(() => {
  const seriesDefinition = [
    { key: 'cpu_percent', name: 'CPU', color: '#3b82f6' },
    { key: 'memory_percent', name: '内存', color: '#8b5cf6' },
    { key: 'disk_percent', name: '磁盘', color: '#f59e0b' },
  ]
  const lastTime = history.value.length ? Date.parse(history.value[history.value.length - 1].timestamp) : Date.now()
  return {
    animation: false,
    legend: { top: 0, right: 0, itemWidth: 16, itemHeight: 8, textStyle: { color: '#64748b', fontSize: 12 } },
    grid: { top: 48, left: 8, right: 12, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis', renderMode: 'richText',
      valueFormatter: (value) => isNumber(value) ? `${value.toFixed(1)}%` : '暂无数据',
      axisPointer: { type: 'line' },
    },
    xAxis: { type: 'time', min: lastTime - 120_000, max: lastTime, splitNumber: 4, axisLabel: { formatter: formatClock, color: '#94a3b8', hideOverlap: true }, axisLine: { lineStyle: { color: '#e2e8f0' } }, axisTick: { show: false }, splitLine: { show: false } },
    yAxis: { type: 'value', min: 0, max: 100, interval: 25, axisLabel: { formatter: '{value}%', color: '#94a3b8' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
    series: seriesDefinition.map((definition) => {
      const points = []
      let previousTime = null
      for (const sample of history.value) {
        const timestamp = Date.parse(sample.timestamp)
        // Break the line when samples were missed instead of inventing continuity.
        if (previousTime !== null && timestamp - previousTime > intervalSeconds.value * 3_000) points.push([previousTime + intervalSeconds.value * 1_000, null])
        points.push([timestamp, isNumber(sample[definition.key]) ? sample[definition.key] : null])
        previousTime = timestamp
      }
      return { name: definition.name, type: 'line', data: points, encode: { x: 0, y: 1, tooltip: [1] }, connectNulls: false, showSymbol: points.length < 2, symbolSize: 5, lineStyle: { width: 2 }, itemStyle: { color: definition.color }, emphasis: { focus: 'series' } }
    }),
  }
})

function clearTimer() {
  if (timer !== null) clearTimeout(timer)
  timer = null
}
function stopClock() {
  if (clockTimer !== null) clearInterval(clockTimer)
  clockTimer = null
}
function startClock() {
  stopClock()
  clockNow.value = Date.now()
  // Keep the age of a paused sample accurate without making any requests.
  if (active && !document.hidden) clockTimer = setInterval(() => { clockNow.value = Date.now() }, 1_000)
}
function scheduleRefresh() {
  clearTimer()
  if (active && autoRefresh.value && !document.hidden && !controller) timer = setTimeout(fetchMetrics, intervalSeconds.value * 1_000)
}
async function fetchMetrics() {
  clearTimer()
  if (!active || document.hidden || controller) return
  if (!user.value.token) {
    error.value = '登录状态已失效，请重新登录。'
    return
  }
  const requestController = new AbortController()
  controller = requestController
  loading.value = true
  clockNow.value = Date.now()
  let timedOut = false
  const timeout = setTimeout(() => { timedOut = true; requestController.abort() }, 12_000)
  try {
    const response = await fetch('/api/system/metrics', { headers: { Authorization: `Bearer ${user.value.token}` }, signal: requestController.signal, cache: 'no-store' })
    if (!response.ok) {
      if (response.status === 401) throw new Error('登录状态已失效，请重新登录。')
      if (response.status === 403) throw new Error('资源监控仅管理员可查看。')
      throw new Error(`暂时无法获取资源指标（${response.status}），请稍后重试。`)
    }
    const data = await response.json()
    if (!data || !data.sampled_at || !data.cpu || !data.memory || !data.disk) throw new Error('服务器返回的资源指标不完整，请稍后重试。')
    if (controller !== requestController || !active) return
    metrics.value = data
    error.value = ''
  } catch (reason) {
    if (controller !== requestController || !active) return
    if (reason.name !== 'AbortError' || timedOut) error.value = timedOut ? `获取资源指标超时，${autoRefresh.value ? '将自动重试' : '请点击立即刷新重试'}。` : reason instanceof TypeError ? `无法连接服务器，${autoRefresh.value ? '将自动重试' : '请点击立即刷新重试'}。` : reason.message || '暂时无法获取资源指标。'
  } finally {
    clearTimeout(timeout)
    if (controller === requestController) {
      controller = null
      loading.value = false
      clockNow.value = Date.now()
      scheduleRefresh()
    }
  }
}
function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) fetchMetrics()
  else clearTimer()
}
function start() {
  if (active) return
  active = true
  startClock()
  if (autoRefresh.value) fetchMetrics()
}
function stop() {
  active = false
  clearTimer()
  stopClock()
  if (controller) controller.abort()
  controller = null
  loading.value = false
}
function handleVisibility() {
  if (!active) return
  if (document.hidden) {
    clearTimer()
    stopClock()
    if (controller) controller.abort()
    controller = null
    loading.value = false
  } else {
    startClock()
    if (autoRefresh.value) fetchMetrics()
  }
}
onMounted(() => { document.addEventListener('visibilitychange', handleVisibility); start() })
onActivated(start)
onDeactivated(stop)
onBeforeUnmount(() => { document.removeEventListener('visibilitychange', handleVisibility); stop() })
</script>
