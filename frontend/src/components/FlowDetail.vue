<template>
  <div class="p-6 max-w-4xl mx-auto">
    <!-- 返回按钮 -->
    <button class="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-5 transition-colors" @click="$emit('back')">
      <span>←</span> 返回流程列表
    </button>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="card p-6 border-red-200 bg-red-50">
      <p class="text-red-700">{{ error }}</p>
      <button class="btn-secondary mt-3 text-xs" @click="loadDetail">重试</button>
    </div>

    <template v-else-if="flow">
      <!-- 流程头部 -->
      <div class="card p-6 mb-5">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">{{ flow.name }}</h1>
            <code class="text-sm text-gray-400 font-mono mt-1 block">ID: {{ flow.id }}</code>
            <p v-if="flow.description" class="text-gray-600 mt-2">{{ flow.description }}</p>
          </div>
          <div class="flex gap-2">
            <span v-if="flow.has_auth" class="badge-info">需认证</span>
            <span class="badge-gray">{{ flow.parameters.length }} 个参数</span>
          </div>
        </div>
      </div>

      <!-- 主体：两列布局 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <!-- 左列：参数表单 + 执行 -->
        <div class="space-y-5">
          <!-- 参数输入表单 -->
          <div class="card p-5">
            <h2 class="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span>⚙️</span> 执行参数
            </h2>

            <div v-if="flow.parameters.length === 0" class="text-sm text-gray-400 text-center py-4">
              该流程无需参数，可直接执行
            </div>

            <div v-else class="space-y-4">
              <div v-for="param in flow.parameters" :key="param.name">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">
                  {{ param.name }}
                  <span v-if="param.required" class="text-red-500 ml-0.5">*</span>
                  <span v-if="param.description" class="font-normal text-gray-400 ml-1 text-xs">— {{ param.description }}</span>
                </label>

                <!-- 枚举 select -->
                <select
                  v-if="param.enum && param.enum.length > 0"
                  v-model="formParams[param.name]"
                  class="input-field"
                >
                  <option value="" disabled>请选择...</option>
                  <option v-for="opt in param.enum" :key="opt" :value="opt">{{ opt }}</option>
                </select>

                <!-- boolean -->
                <div v-else-if="param.type === 'boolean'" class="flex items-center gap-3">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      v-model="formParams[param.name]"
                      class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span class="text-sm text-gray-600">启用</span>
                  </label>
                </div>

                <!-- integer / number -->
                <input
                  v-else-if="param.type === 'integer' || param.type === 'number'"
                  v-model.number="formParams[param.name]"
                  type="number"
                  class="input-field"
                  :placeholder="param.example != null ? String(param.example) : ''"
                />

                <!-- string -->
                <input
                  v-else
                  v-model="formParams[param.name]"
                  type="text"
                  class="input-field"
                  :placeholder="param.example != null ? String(param.example) : ''"
                />

                <!-- 默认值提示 -->
                <p v-if="param.default != null" class="text-xs text-gray-400 mt-1">
                  默认值：{{ param.default }}
                </p>
              </div>
            </div>

            <!-- 执行按钮 -->
            <div class="mt-5 pt-4 border-t border-gray-100">
              <button
                class="btn-primary w-full justify-center"
                :disabled="running"
                @click="runFlow"
              >
                <span v-if="running" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></span>
                <span>{{ running ? '执行中...' : '▶ 执行流程' }}</span>
              </button>
            </div>
          </div>

          <!-- 执行结果 -->
          <div v-if="runResult" class="card p-5">
            <div class="flex items-center justify-between mb-3">
              <h2 class="text-base font-semibold text-gray-800 flex items-center gap-2">
                <span>{{ runResult.status === 'success' ? '✅' : '❌' }}</span>
                执行结果
              </h2>
              <div class="flex items-center gap-3">
                <span :class="runResult.status === 'success' ? 'badge-success' : 'badge-error'">
                  {{ runResult.status === 'success' ? '成功' : '失败' }}
                </span>
                <span class="text-xs text-gray-400">{{ runResult.duration_ms }} ms</span>
              </div>
            </div>

            <!-- 错误信息 -->
            <div v-if="runResult.status === 'error'" class="bg-red-50 border border-red-200 rounded-lg p-3 mb-3">
              <p class="text-sm font-medium text-red-700">{{ runResult.error_code }}</p>
              <p class="text-sm text-red-600 mt-1">{{ runResult.error_message }}</p>
            </div>

            <!-- 返回数据 -->
            <div v-if="runResult.data != null">
              <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">返回数据</p>
              <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-4 overflow-auto max-h-64 font-mono leading-relaxed">{{ JSON.stringify(runResult.data, null, 2) }}</pre>
            </div>
            <div v-else-if="runResult.status === 'success'" class="text-sm text-gray-500 text-center py-2">
              执行成功，无返回数据
            </div>
          </div>
        </div>

        <!-- 右列：YAML 配置预览 -->
        <div class="card p-5">
          <h2 class="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span>📄</span> 流程配置预览
          </h2>
          <div class="space-y-4">
            <!-- 步骤列表 -->
            <div>
              <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">执行步骤 ({{ (flow.steps as unknown[]).length }})</p>
              <div class="space-y-1.5 max-h-48 overflow-auto">
                <div
                  v-for="(step, i) in (flow.steps as Record<string, unknown>[])"
                  :key="i"
                  class="flex items-center gap-2 text-xs bg-gray-50 rounded-md px-3 py-1.5"
                >
                  <span class="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-medium shrink-0 text-xs">{{ i + 1 }}</span>
                  <code class="text-blue-600 font-mono shrink-0">{{ step.type }}</code>
                  <span v-if="step.url" class="text-gray-400 truncate">→ {{ step.url }}</span>
                  <span v-else-if="step.selector" class="text-gray-400 truncate">{{ step.selector }}</span>
                </div>
              </div>
            </div>

            <!-- 完整 JSON 配置 -->
            <div>
              <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">完整配置（JSON）</p>
              <pre class="bg-gray-900 text-gray-300 text-xs rounded-lg p-4 overflow-auto max-h-80 font-mono leading-relaxed">{{ JSON.stringify(flow, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { getFlow, runFlow as apiRunFlow, type FlowDetail, type FlowRunResult } from '../api'

const props = defineProps<{ flowId: string }>()
defineEmits<{ back: [] }>()

const flow = ref<FlowDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const running = ref(false)
const runResult = ref<FlowRunResult | null>(null)
const formParams = reactive<Record<string, unknown>>({})

function initFormParams() {
  if (!flow.value) return
  for (const param of flow.value.parameters) {
    if (param.default != null) {
      formParams[param.name] = param.default
    } else if (param.type === 'boolean') {
      formParams[param.name] = false
    } else {
      formParams[param.name] = ''
    }
  }
}

async function loadDetail() {
  loading.value = true
  error.value = null
  runResult.value = null
  try {
    flow.value = await getFlow(props.flowId)
    initFormParams()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function runFlow() {
  if (!flow.value) return

  // 校验必填参数
  const missing = flow.value.parameters
    .filter((p) => p.required && (formParams[p.name] === '' || formParams[p.name] == null))
    .map((p) => p.name)
  if (missing.length > 0) {
    alert(`请填写必填参数：${missing.join(', ')}`)
    return
  }

  // 构建参数（过滤空字符串可选参数）
  const params: Record<string, unknown> = {}
  for (const param of flow.value.parameters) {
    const v = formParams[param.name]
    if (v !== '' && v != null) {
      params[param.name] = v
    }
  }

  running.value = true
  runResult.value = null
  try {
    runResult.value = await apiRunFlow(props.flowId, params)
  } catch (e) {
    runResult.value = {
      flow_id: props.flowId,
      run_id: null,
      status: 'error',
      duration_ms: 0,
      data: null,
      error_code: 'CLIENT_ERROR',
      error_message: (e as Error).message,
    }
  } finally {
    running.value = false
  }
}

watch(() => props.flowId, loadDetail)
onMounted(loadDetail)
</script>
