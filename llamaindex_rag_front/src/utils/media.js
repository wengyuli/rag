import { t } from '../i18n'

export const mediaKind = (item) => {
  if (item.media_type) return item.media_type
  const extension = String(item.name || item.file_name || '').split('.').pop().toLowerCase()
  if (['jpg', 'jpeg', 'png', 'webp'].includes(extension)) return 'image'
  if (['mp4', 'mov', 'webm', 'mkv'].includes(extension)) return 'video'
  return 'document'
}

export const formatTime = (value) => {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = String(seconds % 60).padStart(2, '0')
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`
}

export const sourceLocation = (source) => {
  if (!source || typeof source !== 'object') return ''
  if (source.start_seconds !== null && source.start_seconds !== undefined) {
    const end = source.end_seconds
    return `${formatTime(source.start_seconds)}${end !== null && end !== undefined && Number(end) > Number(source.start_seconds) ? `–${formatTime(end)}` : ''}`
  }
  return source.page ? t('第 {page} 页', { page: source.page }) : ''
}

export const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]))

// Find an excerpt in the original text, then escape every part before adding our own mark.
export const highlightExcerpt = (text, excerpt) => {
  const original = String(text || '')
  const needle = String(excerpt || '').replace(/\s/g, '').slice(0, 50).toLowerCase()
  if (needle.length < 2) return escapeHtml(original)
  const positions = []
  let normalized = ''
  for (let index = 0; index < original.length; index++) {
    if (!/\s/.test(original[index])) {
      normalized += original[index].toLowerCase()
      positions.push(index)
    }
  }
  const start = normalized.indexOf(needle)
  if (start < 0) return escapeHtml(original)
  const from = positions[start]
  const to = positions[start + needle.length - 1] + 1
  return `${escapeHtml(original.slice(0, from))}<mark id="txt-mark" class="bg-yellow-200 text-slate-900 rounded">${escapeHtml(original.slice(from, to))}</mark>${escapeHtml(original.slice(to))}`
}


// Translate only known service messages. File names, summaries, and excerpts bypass this helper.
export const assetMessage = message => {
  if (message && typeof message === 'object' && message.key) {
    const template = assetMessage(String(message.key))
    return template.replace(/\{(\w+)\}/g, (match, key) => message.values?.[key] == null ? match : String(message.values[key]))
  }
  const source = String(message || '')
  if (['Failed to fetch', 'Load failed', 'NetworkError when attempting to fetch resource.'].includes(source)) return t('网络请求失败，请检查服务后重试。')
  const patterns = [
    [/^正在分析采样画面 (\d+)\/(\d+)$/, '正在分析采样画面 {current}/{total}', match => ({ current: match[1], total: match[2] })],
    [/^识别扫描页 (\d+)\/(\d+)$/, '识别扫描页 {current}/{total}', match => ({ current: match[1], total: match[2] })],
    [/^已读取 (\d+)\/(\d+) 页$/, '已读取 {current}/{total} 页', match => ({ current: match[1], total: match[2] })],
    [/^单个文件不能超过 (\d+) MB$/, '单个文件不能超过 {limit} MB', match => ({ limit: match[1] })],
    [/^PDF 超过 (\d+) 页，请拆分后上传$/, 'PDF 超过 {limit} 页，请拆分后上传', match => ({ limit: match[1] })],
    [/^扫描 PDF 超过 (\d+) 页，请拆分后上传，以控制本地解析耗时$/, '扫描 PDF 超过 {limit} 页，请拆分后上传，以控制本地解析耗时', match => ({ limit: match[1] })],
    [/^本地视觉模型请求失败（HTTP (\d+)），请检查模型是否已安装$/, '本地视觉模型请求失败（HTTP {status}），请检查模型是否已安装', match => ({ status: match[1] })],
    [/^视频时长 ([\d.]+) 秒，超过当前 (\d+) 秒限制，请先分段上传$/, '视频时长 {duration} 秒，超过当前 {limit} 秒限制，请先分段上传', match => ({ duration: match[1], limit: match[2] })],
    [/^(\d+) 页使用视觉模型识别，数字、表格和小字请核对原文。$/, '{count} 页使用视觉模型识别，数字、表格和小字请核对原文。', match => ({ count: match[1] })],
    [/^视频仅采样 (\d+)\/(\d+) 个画面，可能遗漏短暂事件；回答操作步骤时请核对原视频。$/, '视频仅采样 {count}/{total} 个画面，可能遗漏短暂事件；回答操作步骤时请核对原视频。', match => ({ count: match[1], total: match[2] })],
    [/^语音未完成：(.+)$/, '语音未完成：{message}', match => ({ message: assetMessage(match[1]) })],
    [/^([\d:]+) 画面处理失败：(.+)$/, '{time} 画面处理失败：{message}', match => ({ time: match[1], message: assetMessage(match[2]) })],
    [/^视频未提取到可用内容。(.+)$/, '视频未提取到可用内容。{details}', match => ({ details: match[1].split('；').map(assetMessage).join('; ') })],
    [/^配置 (.+) 必须是整数$/, '配置 {name} 必须是整数', match => ({ name: match[1] })],
    [/^配置 (.+) 必须在 1 到 (\d+) 之间$/, '配置 {name} 必须在 1 到 {maximum} 之间', match => ({ name: match[1], maximum: match[2] })],
  ]
  for (const [pattern, key, values] of patterns) {
    const match = source.match(pattern)
    if (match) return t(key, values(match))
  }
  return t(source)
}
