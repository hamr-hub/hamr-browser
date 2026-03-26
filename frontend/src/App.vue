<template>
  <div class="flex h-screen overflow-hidden bg-gray-50">
    <!-- 左侧导航 -->
    <Sidebar :active-view="currentView" @navigate="currentView = $event" />

    <!-- 主内容区 -->
    <main class="flex-1 overflow-auto">
      <FlowList
        v-if="currentView === 'flows'"
        @view-detail="onViewDetail"
      />
      <FlowDetail
        v-else-if="currentView === 'flow-detail'"
        :flow-id="selectedFlowId!"
        @back="currentView = 'flows'"
      />
      <LogList v-else-if="currentView === 'logs'" />
      <BrowserStatus v-else-if="currentView === 'browser'" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import FlowList from './components/FlowList.vue'
import FlowDetail from './components/FlowDetail.vue'
import LogList from './components/LogList.vue'
import BrowserStatus from './components/BrowserStatus.vue'

type View = 'flows' | 'flow-detail' | 'logs' | 'browser'

const currentView = ref<View>('flows')
const selectedFlowId = ref<string | null>(null)

function onViewDetail(flowId: string) {
  selectedFlowId.value = flowId
  currentView.value = 'flow-detail'
}
</script>
