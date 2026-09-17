<template>
  <label :class="['flex items-center gap-2 text-sm', dark ? 'text-slate-300' : 'text-slate-600']">
    <Languages class="h-4 w-4 shrink-0" aria-hidden="true" />
    <span class="sr-only">{{ t('选择界面语言') }}</span>
    <select :value="locale" @change="setLocale($event.target.value)" aria-label="界面语言 / Interface language"
      :class="['min-w-0 flex-1 rounded-lg border px-2.5 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500', dark ? 'border-slate-700 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-700']">
      <option value="zh" lang="zh-CN">简体中文</option>
      <option value="en" lang="en">English</option>
    </select>
  </label>
</template>

<script setup>
import { Languages } from 'lucide-vue-next'
import { useI18n } from '../i18n'
defineProps({ dark: Boolean })
const { t, locale, setLocale } = useI18n()
</script>
