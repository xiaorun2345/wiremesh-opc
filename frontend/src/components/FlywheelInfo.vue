<script setup lang="ts">
import type { TaskResponse, ParseParams } from '@/types'

const props = defineProps<{ task: TaskResponse }>()

// 从 intermediate_data 或 task 中提取 V2 决策信息
// 实际上 parse_params 存在 TaskMemory 里，这里展示任务的基本信息
const engineModeLabel: Record<string, string> = {
  standard: '标准模式',
  recovery: '恢复模式',
  dual:     '双引擎模式',
}
const precisionLabel: Record<string, string> = {
  fast:   '快速',
  normal: '标准',
  high:   '高精度',
}
</script>

<template>
  <div class="flywheel-panel">
    <!-- V2 标识 -->
    <el-card class="card">
      <template #header>
        <div class="card-header">
          <el-icon color="#409eff"><MagicStick /></el-icon>
          <span>V2 智能决策</span>
          <el-tag size="small" type="primary">DecisionAgent</el-tag>
        </div>
      </template>

      <div class="info-item">
        <span class="label">文件类型</span>
        <el-tag size="small">{{ task.file_type.toUpperCase() }}</el-tag>
      </div>
      <div class="info-item">
        <span class="label">任务状态</span>
        <span class="value">{{ task.status }}</span>
      </div>
      <div class="info-item">
        <span class="label">处理进度</span>
        <span class="value">{{ task.progress }}%</span>
      </div>
    </el-card>

    <!-- 飞轮说明 -->
    <el-card class="card">
      <template #header>
        <div class="card-header">
          <el-icon color="#e6a23c"><Refresh /></el-icon>
          <span>数据飞轮</span>
        </div>
      </template>
      <div class="flywheel-desc">
        <div class="flywheel-step">
          <div class="step-dot active" />
          <span>任务执行</span>
        </div>
        <div class="flywheel-arrow">↓</div>
        <div class="flywheel-step">
          <div class="step-dot" />
          <span>结果写回 Memory</span>
        </div>
        <div class="flywheel-arrow">↓</div>
        <div class="flywheel-step">
          <div class="step-dot" />
          <span>下次决策更准</span>
        </div>
      </div>
      <el-alert
        type="info"
        :closable="false"
        style="margin-top: 12px"
      >
        <template #title>
          系统会自动学习每次任务的成功/失败结果，同类文件处理 3 次后开始智能推荐最优引擎。
        </template>
      </el-alert>
    </el-card>

    <!-- 中间数据（PAUSED 时） -->
    <el-card v-if="task.status === 'PAUSED'" class="card warning-card">
      <template #header>
        <div class="card-header">
          <el-icon color="#e6a23c"><Warning /></el-icon>
          <span>等待人工审核</span>
        </div>
      </template>
      <p style="color: #e6a23c; font-size: 13px;">
        任务已暂停，请检查中间数据后点击"续跑任务"继续处理。
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.flywheel-panel { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; gap: 6px; }
.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f5f7fa;
  font-size: 13px;
}
.info-item:last-child { border-bottom: none; }
.label { color: #909399; }
.value { color: #303133; font-weight: 500; }
.flywheel-desc { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.flywheel-step { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #606266; }
.step-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
}
.step-dot.active { background: #409eff; }
.flywheel-arrow { color: #c0c4cc; font-size: 16px; }
.warning-card :deep(.el-card__header) { background: #fdf6ec; }
</style>
