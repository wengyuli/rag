<template>
    <div class="h-full p-8 overflow-y-auto bg-slate-50">
      <div class="max-w-4xl mx-auto">
        <h2 class="text-2xl font-bold text-slate-800 mb-6">{{ t("部门管理") }}</h2>
  
        <!-- 添加部门卡片 -->
        <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-8 flex flex-wrap gap-4 items-end">
          <div class="flex-1 min-w-48">
            <label class="block text-sm font-medium text-slate-700 mb-1">{{ t("新建部门名称") }}</label>
            <input v-model="newDeptName" type="text" :placeholder="t('例如：市场部')"
              class="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <button @click="addDept" :disabled="!newDeptName"
            class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {{ t('添加') }}
          </button>
        </div>
  
        <!-- 部门列表 -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
          <table class="w-full min-w-[600px] text-left">
            <thead class="bg-slate-50 border-b">
              <tr>
                <th class="p-4 text-sm font-semibold text-slate-600 whitespace-nowrap">{{ t("部门名称") }}</th>
                <th class="p-4 text-sm font-semibold text-slate-600 whitespace-nowrap">{{ t("部门 ID") }}</th>
                <th class="p-4 text-sm font-semibold text-slate-600 whitespace-nowrap">{{ t("人员数量") }}</th>
                <th class="p-4 text-right text-sm font-semibold text-slate-600 whitespace-nowrap">{{ t("操作") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in depts" :key="d.id" class="border-b hover:bg-slate-50">
                <td class="p-4 font-medium">{{ displayWorkspace(d.name, d.id) }}</td>
                <td class="p-4 text-slate-500 font-mono text-xs">{{ d.id }}</td>
                <td class="p-4">
                  <span class="bg-blue-100 text-blue-700 px-2 py-1 rounded-full text-xs font-bold">
                    {{ t('{count} 人', { count: d.user_count.toLocaleString(intlLocale) }) }}
                  </span>
                </td>
                <td class="p-4 text-right">
                  <button @click="deleteDept(d)" class="text-red-500 hover:text-red-700 text-sm">{{ t("删除") }}</button>
                </td>
              </tr>
              <tr v-if="depts.length === 0">
                <td colspan="4" class="p-8 text-center text-slate-400">{{ t("暂无部门") }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted } from 'vue'
  import { useAuth } from '../composables/useAuth'
  import { useI18n } from '../i18n'
  
  const { user } = useAuth()
  const { t, intlLocale, displayWorkspace } = useI18n()
  const depts = ref([])
  const newDeptName = ref('')
  
  const fetchDepts = async () => {
    const res = await fetch('/api/admin/departments', {
      headers: { 'Authorization': `Bearer ${user.value.token}` }
    })
    if (res.ok) depts.value = await res.json()
  }
  
  const addDept = async () => {
    const res = await fetch('/api/admin/departments', {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${user.value.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name: newDeptName.value })
    })
    if (res.ok) {
      newDeptName.value = ''
      fetchDepts()
      alert(t('添加成功'))
    } else {
      alert(t('添加失败，可能名称重复'))
    }
  }
  
  const deleteDept = async (dept) => {
    // 🔥 核心需求：弹窗提示级联删除
    const msg = t('⚠️ 危险操作！\n\n删除部门【{name}】将同时删除该部门下的所有【{count}名】员工！\n\n此操作不可恢复，确定要继续吗？', { name: dept.name, count: dept.user_count.toLocaleString(intlLocale.value) })
    if (!confirm(msg)) return
  
    const res = await fetch(`/api/admin/departments/${dept.id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${user.value.token}` }
    })
    if (res.ok) {
      alert(t('删除成功'))
      fetchDepts()
    } else {
      const err = await res.json()
      alert(t(err.detail || '删除失败'))
    }
  }
  
  onMounted(fetchDepts)
  </script>