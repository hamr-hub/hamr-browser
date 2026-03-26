<template>
  <aside class="w-56 bg-gray-900 text-white flex flex-col h-full shrink-0">
    <!-- Logo 区 -->
    <div class="px-5 py-5 border-b border-gray-700">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">H</div>
        <div>
          <div class="text-sm font-semibold text-white leading-tight">hamr-browser</div>
          <div class="text-xs text-gray-400 leading-tight">管理控制台</div>
        </div>
      </div>
    </div>

    <!-- 导航菜单 -->
    <nav class="flex-1 px-3 py-4 space-y-1">
      <button
        v-for="item in navItems"
        :key="item.view"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left"
        :class="activeView === item.view
          ? 'bg-blue-600 text-white'
          : 'text-gray-300 hover:bg-gray-800 hover:text-white'"
        @click="$emit('navigate', item.view)"
      >
        <span class="text-base leading-none">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <!-- 底部版本信息 -->
    <div class="px-5 py-4 border-t border-gray-700">
      <div class="text-xs text-gray-500">版本 v0.2.0</div>
      <div class="text-xs text-gray-500 mt-0.5">API: localhost:8000</div>
    </div>
  </aside>
</template>

<script setup lang="ts">
type View = 'flows' | 'flow-detail' | 'logs' | 'browser'

defineProps<{
  activeView: View
}>()

defineEmits<{
  navigate: [view: View]
}>()

const navItems: { view: View; icon: string; label: string }[] = [
  { view: 'flows',   icon: '⚡', label: '流程管理' },
  { view: 'logs',    icon: '📋', label: '执行日志' },
  { view: 'browser', icon: '🌐', label: '浏览器状态' },
]
</script>
