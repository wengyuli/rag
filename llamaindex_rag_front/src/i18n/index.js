import { computed, ref, watch } from 'vue'
import core from './messages/core.js'
import assets from './messages/assets.js'
import admin from './messages/admin.js'
import chat from './messages/chat.js'

export const LOCALE_KEY = 'enterprise_assets_locale'
const messages = { ...core, ...assets, ...admin, ...chat }
const readLocale = () => {
  try { return localStorage.getItem(LOCALE_KEY) === 'en' ? 'en' : 'zh' }
  catch { return 'zh' }
}
export const locale = ref(readLocale())
export const intlLocale = computed(() => locale.value === 'en' ? 'en-US' : 'zh-CN')
export function setLocale(value) {
  if (!['zh', 'en'].includes(value)) return
  locale.value = value
  try { localStorage.setItem(LOCALE_KEY, value) } catch { /* Keep switching usable without storage. */ }
}
export function t(message, values = {}) {
  const template = locale.value === 'en' && Object.hasOwn(messages, message) ? messages[message] : message
  return String(template).replace(/\{(\w+)\}/g, (match, key) => !Object.hasOwn(values, key) || values[key] == null ? match : String(values[key]))
}
export function displayWorkspace(name, id) {
  if (id === 'global' || name === '公共知识库') return t('公共知识库')
  return name === '未分配部门' ? t(name) : name
}
watch(locale, (value) => {
  if (typeof document === 'undefined') return
  document.documentElement.lang = value === 'en' ? 'en' : 'zh-CN'
  document.title = t('企业数字资产库')
}, { immediate: true })
export function useI18n() { return { t, locale, intlLocale, setLocale, displayWorkspace } }
