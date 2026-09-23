<script setup lang="ts">
import { AGENT_LABELS } from '@/types'
import type { StepStatus } from '@/types'

defineProps<{ steps: StepStatus[] }>()

const STATUS_ICON: Record<string, string> = {
  PENDING: 'Clock',
  RUNNING: 'Refresh',   // Element Plus 有 Refresh，配合 spinning 动画
  SUCCESS: 'CircleCheck',
  FAILED:  'CircleClose',
  SKIPPED: 'Remove',
}

const STATUS_COLOR: Record<string, string> = {
  PENDING: '#c0c4cc',
  RUNNING: '#409eff',
  SUCCESS: '#67c23a',
  FAILED:  '#f56c6c',
  SKIPPED: '#e6a23c',
}
</script>

<template>
  <div class="agent-steps">
    <div
      v-for="(step, idx) in steps"
      :key="step.agent"
      class="step-item"
      :class="step.status.toLowerCase()"
    >
      <div class="step-icon">
        <el-icon
          :size="20"
          :color="STATUS_COLOR[step.status]"
          :class="{ spinning: step.status === 'RUNNING' }"
        >
          <component :is="STATUS_ICON[step.status]" />
        </el-icon>
        <div v-if="idx < steps.length - 1" class="connector" :class="step.status.toLowerCase()" />
      </div>
      <div class="step-content">
        <div class="step-name">
          {{ AGENT_LABELS[step.agent] || step.agent }}
        </div>
        <div class="step-meta">
          <span :style="{ color: STATUS_COLOR[step.status] }">
            {{ step.status === 'RUNNING' ? '执行中...' :
               step.status === 'SUCCESS' ? '完成' :
               step.status === 'FAILED'  ? '失败' :
               step.status === 'SKIPPED' ? '已跳过' : '等待中' }}
          </span>
          <span v-if="step.duration_ms" class="duration">
            {{ step.duration_ms >= 1000
               ? `${(step.duration_ms / 1000).toFixed(1)}s`
               : `${step.duration_ms}ms` }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-steps { padding: 4px 0; }
.step-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
}
.step-icon {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 24px;
}
.connector {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: #e4e7ed;
  margin: 4px 0;
}
.connector.success { background: #67c23a; }
.connector.running { background: linear-gradient(#409eff, #e4e7ed); }
.step-content { flex: 1; padding-top: 2px; }
.step-name { font-size: 14px; color: #303133; font-weight: 500; }
.step-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
  font-size: 12px;
}
.duration { color: #909399; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 1s linear infinite; }
</style>
