<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { ElMessage, ElMessageBox } from 'element-plus'
import { STATUS_TYPE, STATUS_LABEL, AGENT_LABELS } from '@/types'
import type { TaskStatus } from '@/types'
import AgentSteps from '@/components/AgentSteps.vue'
import FlywheelInfo from '@/components/FlywheelInfo.vue'
import FilePreview from '@/components/FilePreview.vue'

const route     = useRoute()
const router    = useRouter()
const taskStore = useTaskStore()

const taskId    = route.params.id as string
const task      = computed(() => taskStore.currentTask)
const resumeData = ref<string>('{}')  // JSON 字符串，提交时解析
const showResume = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

const TERMINAL = ['SUCCESS', 'FAILED', 'PAUSED', 'CANCELLED']

onMounted(async () => {
  await taskStore.fetchTask(taskId)
  startPolling()
})

onUnmounted(() => stopPolling())

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    if (!task.value || TERMINAL.includes(task.value.status)) {
      stopPolling()
      return
    }
    await taskStore.fetchTask(taskId)
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleResume() {
  let data: Record<string, unknown> = {}
  try {
    if (resumeData.value.trim()) {
      data = JSON.parse(resumeData.value)
    }
  } catch {
    ElMessage.error('JSON 格式错误，请检查修正数据')
    return
  }
  await taskStore.resumeTask(taskId, data)
  showResume.value = false
  startPolling()
  ElMessage.success('已续跑')
}

async function handleCancel() {
  await ElMessageBox.confirm('确定取消该任务？', '提示', { type: 'warning' })
  await taskStore.cancelTask(taskId)
  ElMessage.success('已取消')
}
</script>

<template>
  <div class="detail-page" v-if="task">
    <!-- 顶部 -->
    <div class="page-header">
      <el-button text @click="router.push('/')">
        <el-icon><ArrowLeft /></el-icon> 返回列表
      </el-button>
      <div class="header-info">
        <h2>{{ task.file_name }}</h2>
        <el-tag :type="STATUS_TYPE[task.status as TaskStatus]" size="large">
          {{ STATUS_LABEL[task.status as TaskStatus] }}
        </el-tag>
      </div>
    </div>

    <div class="content">
      <!-- 左侧：进度和步骤 -->
      <div class="main-panel">
        <!-- 文件预览 -->
        <FilePreview
          :file-type="task.file_type"
          :file-name="task.file_name"
          :task-id="taskId"
        />

        <!-- 总进度 -->
        <el-card class="card">
          <template #header><span>处理进度</span></template>
          <el-progress
            :percentage="task.progress"
            :status="task.status === 'SUCCESS' ? 'success' : task.status === 'FAILED' ? 'exception' : undefined"
            :stroke-width="12"
            style="margin-bottom: 12px"
          />
          <div class="meta-row">
            <span>文件类型：<el-tag size="small">{{ task.file_type.toUpperCase() }}</el-tag></span>
            <span>当前步骤：{{ task.current_step ? AGENT_LABELS[task.current_step] || task.current_step : '—' }}</span>
            <span>创建时间：{{ new Date(task.created_at).toLocaleString('zh-CN') }}</span>
          </div>
        </el-card>

        <!-- Agent 步骤 -->
        <el-card class="card">
          <template #header><span>执行步骤</span></template>
          <AgentSteps :steps="task.steps" />
        </el-card>

        <!-- 错误信息 -->
        <el-alert
          v-if="task.status === 'FAILED' && task.error_msg"
          type="error"
          :title="task.error_msg"
          :closable="false"
          class="card"
        />

        <!-- PAUSED：人工审核数据 -->
        <el-card v-if="task.status === 'PAUSED' && task.intermediate_data" class="card">
          <template #header>
            <span>⚠️ 需要人工审核</span>
          </template>
          <p class="review-hint">{{ (task.intermediate_data as any).review_hint }}</p>
          <el-collapse>
            <el-collapse-item title="查看中间数据">
              <pre class="json-view">{{ JSON.stringify(task.intermediate_data, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-card>

        <!-- 操作按钮 -->
        <div class="actions">
          <el-button
            v-if="task.status === 'SUCCESS'"
            type="primary" size="large"
            @click="router.push(`/tasks/${taskId}/report`)"
          >
            <el-icon><Download /></el-icon> 查看报告
          </el-button>
          <el-button
            v-if="['FAILED', 'PAUSED'].includes(task.status)"
            type="warning" size="large"
            @click="showResume = true"
          >
            <el-icon><RefreshRight /></el-icon> 续跑任务
          </el-button>
          <el-button
            v-if="['RUNNING', 'PENDING', 'PAUSED'].includes(task.status)"
            type="danger" size="large" plain
            @click="handleCancel"
          >
            <el-icon><Close /></el-icon> 取消任务
          </el-button>
        </div>
      </div>

      <!-- 右侧：V2 飞轮信息 -->
      <div class="side-panel">
        <FlywheelInfo :task="task" />
      </div>
    </div>

    <!-- 续跑对话框 -->
    <el-dialog v-model="showResume" title="续跑任务" width="500px">
      <p style="margin-bottom: 16px; color: #606266;">
        可选择性传入修正数据，留空则直接从失败步骤重试。
      </p>
      <el-input
        v-model="resumeData"
        type="textarea"
        :rows="6"
        placeholder='{"floor_height": 3000, "materials": ["瓷砖"]}'
      />
      <template #footer>
        <el-button @click="showResume = false">取消</el-button>
        <el-button type="primary" @click="handleResume">确认续跑</el-button>
      </template>
    </el-dialog>
  </div>

  <div v-else class="loading-page">
    <el-skeleton :rows="8" animated />
  </div>
</template>

<style scoped>
.detail-page { min-height: 100vh; background: #f5f7fa; padding: 24px; }
.page-header { margin-bottom: 20px; }
.header-info { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.header-info h2 { font-size: 22px; color: #303133; }
.content { display: grid; grid-template-columns: 1fr 320px; gap: 20px; }
.card { margin-bottom: 16px; }
.meta-row { display: flex; gap: 24px; flex-wrap: wrap; color: #606266; font-size: 14px; }
.review-hint { color: #e6a23c; margin-bottom: 12px; }
.json-view {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  overflow: auto;
  max-height: 300px;
}
.actions { display: flex; gap: 12px; flex-wrap: wrap; }
.loading-page { padding: 40px; max-width: 800px; margin: 0 auto; }
@media (max-width: 900px) {
  .content { grid-template-columns: 1fr; }
}
</style>
