<template>
  <div class="p-6 max-w-6xl mx-auto">
    <!-- 页头 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">执行日志</h1>
        <p class="text-sm text-gray-500 mt-1">查看历史执行记录及结果</p>
      </div>
      <button class="btn-secondary" @click="loadLogs">
        <span class="mr-1.5">🔄</span> 刷新
      </button>
    </div>

    <!-- 过滤条件 -->
    <div class="card p-4 mb-5 flex flex-wrap gap-4 items-end">
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">流程 ID</label>
        <input
          v-model="filterFlowId"
          type="text"
          placeholder="全部流程"
          class="input-field w-44"
          @keyup.enter="loadLogs"
        />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">状态</label>
        <select v-model="filterStatus" class="input-field w-32">
          <option value="">全部</option>
          <option value="success">成功</option>
          <option value="error">失败</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">条数限制</label>
        <select v-model.number="filterLimit" class="input-field w-24">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
        </select>
      </div>
      <button class="btn-primary" @click="loadLogs">查询</button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex justify-center py-20">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="card p-6 bg-red-50 border-red-200">
      <p class="text-red-700">{{ error }}</p>
      <button class="btn-secondary mt-3 text-xs" @click="loadLogs">重试</button>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="card p-12 text-center">
      <div class="text-5xl mb-4">📭</div>
      <p class="text-lg font-medium text-gray-700">暂无执行记录</p>
      <p class="text-sm text-gray-500 mt-2">执行流程后，历史记录将显示在这里</p>
    </div>

    <!-- 统计信息 -->
    <div v-else>
      <div class="flex items-center justify-between mb-4">
        <p class="text-sm text-gray-500">共 <span class="font-medium text-gray-800">{{ total }}</span> 条记录</p>
        <div class="flex gap-4 text-xs text-gray-500">
          <span>成功：<span class="text-green-600 font-medium">{{ successCount }}</span></span>
          <span>失败：<span class="text-red-600 font-medium">{{ errorCount }}</span></span>
          <span v-if="avgDuration > 0">平均耗时：<span class="font-medium">{{ avgDuration }} ms</span></span>
        </div>
      </div>

      <!-- 日志列表 -->
      <div class="card overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 border-b border-gray-200">
            <tr>
              <th class="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide w-32">状态</th>
              <th class="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">流程</th>
              <th class="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">时间</th>
              <th class="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide w-24">耗时</th>
              <th class="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">详情</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="record in records"
              :key="record.run_id"
              class="hover:bg-gray-50 cursor-pointer transition-colors"
              @click="selectedRecord = record"
            >
              <td class="px-4 py-3">
                <span :class="record.status === 'success' ? 'badge-success' : 'badge-error'">
                  {{ record.status === 'success' ? '✓ 成功' : '✗ 失败' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <code class="text-blue-600 font-mono text-xs bg-blue-50 px-1.5 py-0.5 rounded">{{ record.flow_id }}</code>
              </td>
              <td class="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{{ record.created_at }}</td>
              <td class="px-4 py-3 text-right font-mono text-xs text-gray-600">{{ record.duration_ms }} ms</td>
              <td class="px-4 py-3">
                <span v-if="record.status === 'error'" class="text-red-500 text-xs truncate max-w-xs block">
                  {{ record.error_message }}
                </span>
                <span v-else class="text-gray-400 text-xs">
                  {{ record.data != null ? '有返回数据' : '无返回数据' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div
      v-if="selectedRecord"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="selectedRecord = null"
    >
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden">
        <!-- 弹窗头部 -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div class="flex items-center gap-3">
            <span :class="selectedRecord.status === 'success' ? 'badge-success' : 'badge-error'">
              {{ selectedRecord.status === 'success' ? '成功' : '失败' }}
            </span>
            <code class="text-sm font-mono text-gray-700">{{ selectedRecord.flow_id }}</code>
          </div>
          <button class="text-gray-400 hover:text-gray-700 text-xl" @click="selectedRecord = null">×</button>
        </div>

        <!-- 弹窗内容 -->
        <div class="flex-1 overflow-auto p-6 space-y-4">
          <!-- 基本信息 -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-400 mb-1">Run ID</p>
              <code class="text-xs font-mono text-gray-700 break-all">{{ selectedRecord.run_id }}</code>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-400 mb-1">耗时</p>
              <p class="font-mono text-gray-700">{{ selectedRecord.duration_ms }} ms</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-400 mb-1">执行时间</p>
              <p class="text-gray-700 text-xs">{{ selectedRecord.created_at }}</p>
            </div>
          </div>

          <!-- 错误信息 -->
          <div v-if="selectedRecord.status === 'error'" class="bg-red-50 border border-red-200 rounded-lg p-4">
            <p class="text-xs font-semibold text-red-700 mb-1">错误代码：{{ selectedRecord.error_code }}</p>
            <p class="text-sm text-red-600">{{ selectedRecord.error_message }}</p>
          </div>

          <!-- 请求参数 -->
          <div>
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">请求参数</p>
            <pre class="bg-gray-900 text-gray-300 text-xs rounded-lg p-4 overflow-auto max-h-40 font-mono">{{ JSON.stringify(selectedRecord.params, null, 2) }}</pre>
          </div>

          <!-- 返回数据 -->
          <div v-if="selectedRecord.data != null">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">返回数据</p>
            <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-4 overflow-auto max-h-48 font-mono">{{ JSON.stringify(selectedRecord.data, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getLogs, type HistoryRecord } from '../api'

const records = ref<HistoryRecord[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)
const selectedRecord = ref<HistoryRecord | null>(null)

const filterFlowId = ref('')
const filterStatus = ref<'' | 'success' | 'error'>('')
const filterLimit = ref(50)

const successCount = computed(() => records.value.filter((r) => r.status === 'success').length)
const errorCount = computed(() => records.value.filter((r) => r.status === 'error').length)
const avgDuration = computed(() => {
  if (records.value.length === 0) return 0
  const sum = records.value.reduce((acc, r) => acc + r.duration_ms, 0)
  return Math.round(sum / records.value.length)
})

async function loadLogs() {
  loading.value = true
  error.value = null
  try {
    const res = await getLogs({
      flow_id: filterFlowId.value || undefined,
      status: filterStatus.value || undefined,
      limit: filterLimit.value,
    })
    records.value = res.records
    total.value = res.total
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(loadLogs)
</script>
