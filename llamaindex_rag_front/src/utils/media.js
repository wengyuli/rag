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
  return source.page ? `第 ${source.page} 页` : ''
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
