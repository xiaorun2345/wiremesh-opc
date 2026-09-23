<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'

const router    = useRouter()
const taskStore = useTaskStore()

const uploading  = ref(false)
const fileList   = ref<UploadFile[]>([])

const ALLOWED_EXTS = ['pdf', 'dwg', 'dxf', 'jpg', 'jpeg', 'png']
const MAX_SIZE_MB  = 100

function beforeUpload(file: File) {
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (!ALLOWED_EXTS.includes(ext)) {
    ElMessage.error(`不支持的文件格式，支持：${ALLOWED_EXTS.join('/')}`)
    return false
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    ElMessage.error(`文件超过 ${MAX_SIZE_MB}MB 限制`)
    return false
  }
  return true
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  const rawFile = fileList.value[0].raw
  if (!rawFile) return

  uploading.value = true
  try {
    const taskId = await taskStore.uploadFile(rawFile)
    ElMessage.success('上传成功，正在处理...')
    router.push(`/tasks/${taskId}`)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="upload-page">
    <div class="upload-card">
      <div class="back-btn">
        <el-button text @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
      </div>

      <h2>上传图纸</h2>
      <p class="subtitle">支持 PDF、DWG、DXF、JPG、PNG 格式，最大 100MB</p>

      <el-upload
        v-model:file-list="fileList"
        drag
        :auto-upload="false"
        :limit="1"
        :before-upload="beforeUpload"
        accept=".pdf,.dwg,.dxf,.jpg,.jpeg,.png"
        class="uploader"
      >
        <el-icon size="48" color="#c0c4cc"><UploadFilled /></el-icon>
        <div class="upload-text">
          <p>拖拽文件到此处，或 <em>点击上传</em></p>
          <p class="hint">PDF / DWG / DXF / JPG / PNG，≤ 100MB</p>
        </div>
      </el-upload>

      <!-- 文件预览 -->
      <div v-if="fileList.length > 0" class="file-preview">
        <el-icon><Document /></el-icon>
        <span>{{ fileList[0].name }}</span>
        <span class="size">{{ ((fileList[0].size || 0) / 1024 / 1024).toFixed(2) }} MB</span>
      </div>

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="handleUpload"
          style="width: 200px"
        >
          <el-icon><Upload /></el-icon>
          {{ uploading ? '上传中...' : '开始处理' }}
        </el-button>
      </div>

      <!-- 说明 -->
      <el-alert type="info" :closable="false" class="tip">
        <template #title>
          <strong>V2 智能模式</strong>：系统将自动分析图纸质量，选择最优解析策略，并通过飞轮机制持续优化。
        </template>
      </el-alert>
    </div>
  </div>
</template>

<style scoped>
.upload-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.upload-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 560px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.back-btn { margin-bottom: 16px; }
h2 { font-size: 24px; color: #303133; margin-bottom: 8px; }
.subtitle { color: #909399; margin-bottom: 24px; }
.uploader { width: 100%; }
:deep(.el-upload-dragger) {
  padding: 40px;
  border-radius: 12px;
}
.upload-text { margin-top: 12px; }
.upload-text p { color: #606266; }
.upload-text em { color: #409eff; font-style: normal; }
.hint { font-size: 12px; color: #c0c4cc; margin-top: 4px; }
.file-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f0f7ff;
  border-radius: 8px;
  margin-top: 16px;
  color: #409eff;
}
.size { margin-left: auto; color: #909399; font-size: 12px; }
.actions { text-align: center; margin: 24px 0; }
.tip { margin-top: 16px; }
</style>
