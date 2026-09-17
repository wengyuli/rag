/**
 * 用户认证管理模块
 *
 * 该模块提供用户登录、登出、权限验证等核心认证功能
 * 负责管理用户状态、Token存储、路由守卫等
 *
 * @author Guo Lijian
 * @version 1.0.0
 * @since 2025-12-06
 */

import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspace } from './useWorkspace'

// Keep interface preferences when ending or recovering an authenticated session.
const clearAuthStorage = () => {
  for (const key of ['user_info', 'access_token', 'last_session_id', 'activeTab']) localStorage.removeItem(key)
}

// 全局状态
const user = ref({
  username: '',
  role: 'member',
  token: '',
  id: null,
  dept_id: null,   //新增
  dept_name: ''    //新增
})

export function useAuth() {
  const router = useRouter()
  // 获取 setWorkspace 方法
  const { setWorkspace } = useWorkspace()

  // --- 🔥 核心修复：初始化时恢复工作区状态 ---
  // 这段代码会在文件被引入时立即执行
  const initAuth = () => {
    const storedUser = localStorage.getItem('user_info')
    const storedToken = localStorage.getItem('access_token')

    if (storedUser && storedToken) {
      try {
        const u = JSON.parse(storedUser)
        // 1. 恢复用户状态
        user.value = { ...u, token: storedToken }
        
        // 2. 🔥 恢复工作区状态 (解决刷新变回公共库的问题)
        if (u.dept_id) {
          setWorkspace({
            id: u.dept_id,
            name: u.dept_name,
            role: u.role
          })
        }
      } catch(e) { 
        console.error("恢复登录态失败", e)
        clearAuthStorage()
      }
    }
  }

  // 登录逻辑
  const login = async (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)

    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '登录失败')
    }

    const data = await res.json()
    const userInfo = data.user_info // 后端返回的完整信息

    // 1. 更新用户状态 (补充保存 dept 信息)
    user.value = {
      username: userInfo.name,
      role: userInfo.role,
      id: userInfo.id,
      dept_id: userInfo.dept_id,     // 保存部门ID
      dept_name: userInfo.dept_name, // 保存部门名称
      token: data.access_token
    }

    // 2. 持久化存储
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user_info', JSON.stringify(user.value))

    // 3. 设置工作区
    setWorkspace({
      id: userInfo.dept_id,
      name: userInfo.dept_name,
      role: userInfo.role
    })

    return true
  }

  // 退出登录
  const logout = () => {
    user.value = { username: '', role: 'member', token: '', id: null }
    clearAuthStorage()
    // 退出时重置为公共
    setWorkspace({ id: 'global', name: '公共知识库' }) 
    router.push('/')
  }

  // 暴露 initAuth 供 main.js 调用，或者在这里直接执行
  return {
    user,
    login,
    logout,
    initAuth 
  }
}