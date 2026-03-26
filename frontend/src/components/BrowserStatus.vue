<template>
  <div class="p-6 max-w-4xl mx-auto">
    <!-- 页头 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">浏览器状态</h1>
        <p class="text-sm text-gray-500 mt-1">监控 Playwright 浏览器实例状态</p>
      </div>
      <div class="flex gap-3">
        <button class="btn-secondary" @click="loadStatus">
          <span class="mr-1.5">🔄</span> 刷新
        </button>
        <button
          class="btn-danger"
          :disabled="restarting"
          @click="onRestart"
        >
          <span v-if="restarting" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></span>
          <span>{{ restarting ? '重启中...' : '🔁 重启浏览器' }}</span>
        </button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex justify-center py-20">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="card p-6 bg-red-50 border-red-200">
      <div class="flex items-start gap-3">
        <span class="text-red-500 text-xl">⚠️</span>
        <div>
          <p class="font-medium text-red-800">无法获取浏览器状态</p>
          <p class="text-sm text-red-600 mt-1">{{ error }}</p>
          <p class="text-xs text-red-500 mt-2">请确认后端服务 (localhost:8000) 是否正常运行</p>
          <button class="btn-secondary mt-3 text-xs" @click="loadStatus">重试</button>
        </div>
      </div>
    </div>

    <template v-else-if="status">
      <!-- 状态卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <!-- 浏览器在线状态 -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-medium text-gray-500">浏览器状态</p>
            <span class="text-2xl">{{ status.ready ? '🟢' : '🔴' }}</span>
          </div>
          <p class="text-2xl font-bold" :class="status.ready ? 'text-green-600' : 'text-red-600'">
            {{ status.ready ? '运行中' : '离线' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">Playwright Chromium</p>
        </div>

        <!-- 运行模式 -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-medium text-gray-500">运行模式</p>
            <span class="text-2xl">{{ status.headless ? '🖥️' : '👁️' }}</span>
          </div>
          <p class="text-2xl font-bold text-gray-800">
            {{ status.headless ? 'Headless' : 'Headed' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">{{ status.headless ? '无界面模式' : '有界面模式' }}</p>
        </div>

        <!-- 健康检查 -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-medium text-gray-500">API 服务</p>
            <span class="text-2xl">{{ health ? '✅' : '❓' }}</span>
          </div>
          <p class="text-2xl font-bold text-gray-800">
            {{ health?.status === 'ok' ? '正常' : '异常' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">版本 {{ health?.version ?? '-' }}</p>
        </div>
      </div>

      <!-- 流程登录状态 -->
      <div class="card p-5 mb-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-800 flex items-center gap-2">
            <span>🔐</span> 流程登录状态
          </h2>
          <button class="btn-secondary text-xs" @click="loadLoginStatuses">检查所有</button>
        </div>

        <div v-if="loginStatuses.length === 0" class="text-center py-6 text-gray-400 text-sm">
          点击「检查所有」查看各流程登录状态
        </div>

        <div v-else class="space-y-2">
          <div
            v-for="ls in loginStatuses"
            :key="ls.flow_id"
            class="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-lg"
          >
            <div class="flex items-center gap-3">
              <span class="text-sm" :class="ls.logged_in ? 'text-green-500' : 'text-red-500'">
                {{ ls.logged_in ? '✓' : '✗' }}
              </span>
              <code class="text-sm font-mono text-gray-700">{{ ls.flow_id }}</code>
              <span v-if="!ls.has_auth" class="badge-gray text-xs">无需认证</span>
            </div>
            <div class="flex items-center gap-2">
              <span :class="ls.logged_in ? 'badge-success' : 'badge-error'">
                {{ ls.logged_in ? '已登录' : '未登录' }}
              </span>
              <button
                v-if="ls.has_auth && !ls.logged_in"
                class="btn-primary text-xs py-1 px-2"
                :disabled="loginInProgress === ls.flow_id"
                @click="onTriggerLogin(ls.flow_id)"
              >
                {{ loginInProgress === ls.flow_id ? '登录中...' : '触发登录' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速操作 -->
      <div class="card p-5">
        <h2 class="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span>⚡</span> 快速操作
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            class="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
            @click="onRestart"
            :disabled="restarting"
          >
            <span class="text-2xl">🔁</span>
            <div>
              <p class="text-sm font-medium text-gray-800">重启浏览器</p>
              <p class="text-xs text-gray-400">清理状态，重新初始化 Playwright</p>
            </div>
          </button>
          <button
            class="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
            @click="loadStatus"
          >
            <span class="text-2xl">🔄</span>
            <div>
              <p class="text-sm font-medium text-gray-800">刷新状态</p>
              <p class="text-xs text-gray-400">重新拉取浏览器及 API 服务状态</p>
            </div>
          </button>
        </div>
      </div>
    </template>

    <!-- Toast 提示 -->
    <div
      v-if="toast"
      class="fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-sm font-medium"
      :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getBrowserStatus,
  restartBrowser,
  getHealth,
  getFlows,
  checkLoginStatus,
  triggerLogin,
  type BrowserStatus,
} from '../api'

const status = ref<BrowserStatus | null>(null)
const health = ref<{ status: string; version: string; browser_ready: boolean } | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const restarting = ref(false)
const loginInProgress = ref<string | null>(null)
const toast = ref<{ type: 'success' | 'error'; message: string } | null>(null)

interface LoginStatus {
  flow_id: string
  has_auth: boolean
  logged_in: boolean
}
const loginStatuses = ref<LoginStatus[]>([])

function showToast(type: 'success' | 'error', message: string) {
  toast.value = { type, message }
  setTimeout(() => { toast.value = null }, 3000)
}

async function loadStatus() {
  loading.value = true
  error.value = null
  try {
    const [s, h] = await Promise.all([getBrowserStatus(), getHealth()])
    status.value = s
    health.value = h
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function loadLoginStatuses() {
  try {
    const flows = await getFlows()
    const results = await Promise.allSettled(
      flows.map((f) => checkLoginStatus(f.id))
    )
    loginStatuses.value = results
      .map((r, i) => {
        if (r.status === 'fulfilled') return r.value
        return { flow_id: flows[i].id, has_auth: false, logged_in: false }
      })
  } catch (e) {
    showToast('error', `检查登录状态失败：${(e as Error).message}`)
  }
}

async function onRestart() {
  if (!confirm('确认重启浏览器？正在执行的流程将被中断。')) return
  restarting.value = true
  try {
    await restartBrowser()
    showToast('success', '浏览器重启成功')
    await loadStatus()
  } catch (e) {
    showToast('error', `重启失败：${(e as Error).message}`)
  } finally {
    restarting.value = false
  }
}

async function onTriggerLogin(flowId: string) {
  loginInProgress.value = flowId
  try {
    await triggerLogin(flowId)
    showToast('success', `流程 ${flowId} 登录成功`)
    // 刷新登录状态
    const updated = await checkLoginStatus(flowId)
    const idx = loginStatuses.value.findIndex((s) => s.flow_id === flowId)
    if (idx >= 0) loginStatuses.value[idx] = updated
  } catch (e) {
    showToast('error', `登录失败：${(e as Error).message}`)
  } finally {
    loginInProgress.value = null
  }
}

onMounted(loadStatus)
</script>
