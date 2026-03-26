<template>
  <div class="p-6 max-w-6xl mx-auto">
    <!-- 页头 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">流程管理</h1>
        <p class="text-sm text-gray-500 mt-1">管理所有已注册的 Playwright 自动化流程</p>
      </div>
      <div class="flex gap-3">
        <button class="btn-secondary" @click="loadFlows">
          <span class="mr-1.5">🔄</span> 刷新
        </button>
        <label class="btn-primary cursor-pointer">
          <span class="mr-1.5">📤</span> 上传流程
          <input type="file" accept=".yaml,.yml" class="hidden" @change="onFileUpload" />
        </label>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="flex flex-col items-center gap-3">
        <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-sm text-gray-500">加载中...</p>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="card p-6 border-red-200 bg-red-50">
      <div class="flex items-start gap-3">
        <span class="text-red-500 text-xl">⚠️</span>
        <div>
          <p class="font-medium text-red-800">加载失败</p>
          <p class="text-sm text-red-600 mt-1">{{ error }}</p>
          <button class="btn-secondary mt-3 text-xs" @click="loadFlows">重试</button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="flows.length === 0" class="card p-12 text-center">
      <div class="text-5xl mb-4">📭</div>
      <p class="text-lg font-medium text-gray-700">暂无注册流程</p>
      <p class="text-sm text-gray-500 mt-2">上传 YAML 配置文件来注册新流程</p>
    </div>

    <!-- 流程卡片列表 -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <div
        v-for="flow in flows"
        :key="flow.id"
        class="card p-5 hover:shadow-md transition-shadow cursor-pointer group"
        @click="$emit('view-detail', flow.id)"
      >
        <!-- 卡片头部 -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex-1 min-w-0">
            <h3 class="font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
              {{ flow.name }}
            </h3>
            <code class="text-xs text-gray-400 font-mono">{{ flow.id }}</code>
          </div>
          <div class="flex gap-1.5 ml-3 shrink-0">
            <span v-if="flow.has_auth" class="badge-info">需认证</span>
          </div>
        </div>

        <!-- 描述 -->
        <p class="text-sm text-gray-500 line-clamp-2 mb-4 min-h-[2.5rem]">
          {{ flow.description || '暂无描述' }}
        </p>

        <!-- 元信息 -->
        <div class="flex items-center justify-between text-xs text-gray-400 border-t border-gray-100 pt-3">
          <span>参数数量：{{ flow.parameter_count }}</span>
          <div class="flex gap-2" @click.stop>
            <button
              class="text-blue-500 hover:text-blue-700 font-medium transition-colors"
              @click="$emit('view-detail', flow.id)"
            >
              详情
            </button>
            <span class="text-gray-300">|</span>
            <button
              class="text-red-500 hover:text-red-700 font-medium transition-colors"
              :disabled="deletingId === flow.id"
              @click="onDelete(flow.id)"
            >
              {{ deletingId === flow.id ? '删除中...' : '删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传成功/失败 Toast -->
    <div
      v-if="toast"
      class="fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all"
      :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getFlows, deleteFlow, uploadFlow, type FlowSummary } from '../api'

defineEmits<{
  'view-detail': [flowId: string]
}>()

const flows = ref<FlowSummary[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const toast = ref<{ type: 'success' | 'error'; message: string } | null>(null)

function showToast(type: 'success' | 'error', message: string) {
  toast.value = { type, message }
  setTimeout(() => { toast.value = null }, 3000)
}

async function loadFlows() {
  loading.value = true
  error.value = null
  try {
    flows.value = await getFlows()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function onDelete(flowId: string) {
  if (!confirm(`确认删除流程「${flowId}」？此操作不可撤销。`)) return
  deletingId.value = flowId
  try {
    await deleteFlow(flowId)
    flows.value = flows.value.filter((f) => f.id !== flowId)
    showToast('success', `流程「${flowId}」已删除`)
  } catch (e) {
    showToast('error', `删除失败：${(e as Error).message}`)
  } finally {
    deletingId.value = null
  }
}

async function onFileUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const result = await uploadFlow(file)
    showToast('success', result.message)
    await loadFlows()
  } catch (e) {
    showToast('error', `上传失败：${(e as Error).message}`)
  }
  // reset input
  ;(e.target as HTMLInputElement).value = ''
}

onMounted(loadFlows)
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
