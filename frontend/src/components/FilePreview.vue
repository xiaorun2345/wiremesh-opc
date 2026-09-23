<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const props = defineProps<{
  fileType: string
  fileName: string
  taskId: string
}>()

// Mock 模式下用占位图，真实模式从后端获取
const USE_MOCK = (import.meta.env.VITE_USE_MOCK === 'true') ||
  (typeof window !== 'undefined' && (window as any).__USE_MOCK__)

const previewUrl = ref<string | null>(null)
const loading    = ref(false)
const error      = ref(false)

const isImage = computed(() => ['jpg', 'jpeg', 'png'].includes(props.fileType))
const isPdf   = computed(() => props.fileType === 'pdf')
const isCad   = computed(() => ['dwg', 'dxf'].includes(props.fileType))

const fileIcon = computed(() => {
  if (isImage.value) return 'Picture'
  if (isPdf.value)   return 'Document'
  if (isCad.value)   return 'Grid'
  return 'Document'
})

const fileColor = computed(() => {
  if (isImage.value) return '#67c23a'
  if (isPdf.value)   return '#f56c6c'
  if (isCad.value)   return '#409eff'
  return '#909399'
})

onMounted(async () => {
  if (!isImage.value && !isPdf.value) return
  if (USE_MOCK) {
    // Mock 模式：图片用占位图，PDF 用示例
    if (isImage.value) {
      previewUrl.value = `https://picsum.photos/seed/${props.taskId}/600/400`
    }
    return
  }
  // 真实模式：从后端获取文件预览
  loading.value = true
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`/api/v2/tasks/${props.taskId}/file`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error('获取失败')
    const blob = await res.blob()
    previewUrl.value = URL.createObjectURL(blob)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})

async function downloadFile() {
  if (USE_MOCK) {
    // Mock 模式：提示
    import('element-plus').then(({ ElMessage }) => {
      ElMessage.info('Mock 模式下原始文件下载不可用')
    })
    return
  }
  const token = localStorage.getItem('access_token')
  const res = await fetch(`/api/v2/tasks/${props.taskId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const blob = await res.blob()
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = props.fileName
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <el-card class="file-preview-card">
    <template #header>
      <div class="card-header">
        <el-icon :color="fileColor" size="18"><component :is="fileIcon" /></el-icon>
        <span>原始文件</span>
        <el-button size="small" text @click="downloadFile" style="margin-left: auto">
          <el-icon><Download /></el-icon> 下载原文件
        </el-button>
      </div>
    </template>

    <!-- 文件基本信息 -->
    <div class="file-info">
      <span class="file-name">{{ fileName }}</span>
      <el-tag size="small" :type="isCad ? 'primary' : isPdf ? 'danger' : 'success'">
        {{ fileType.toUpperCase() }}
      </el-tag>
    </div>

    <!-- 图片预览 -->
    <div v-if="isImage" class="preview-area">
      <div v-if="loading" class="preview-loading">
        <el-icon class="spinning" size="32" color="#c0c4cc"><Refresh /></el-icon>
        <span>加载中...</span>
      </div>
      <el-image
        v-else-if="previewUrl"
        :src="previewUrl"
        fit="contain"
        class="preview-image"
        :preview-src-list="[previewUrl]"
        preview-teleported
      >
        <template #error>
          <div class="preview-error">
            <el-icon size="40" color="#c0c4cc"><Picture /></el-icon>
            <span>图片加载失败</span>
          </div>
        </template>
      </el-image>
      <div v-else-if="error" class="preview-error">
        <el-icon size="40" color="#c0c4cc"><Picture /></el-icon>
        <span>无法加载预览</span>
      </div>
    </div>

    <!-- PDF 提示 -->
    <div v-else-if="isPdf" class="preview-placeholder pdf">
      <el-icon size="48" color="#f56c6c"><Document /></el-icon>
      <p>PDF 施工图</p>
      <p class="hint">点击右上角下载查看完整文件</p>
    </div>

    <!-- CAD 文件提示 -->
    <div v-else-if="isCad" class="preview-placeholder cad">
      <el-icon size="48" color="#409eff"><Grid /></el-icon>
      <p>{{ fileType.toUpperCase() }} 图纸</p>
      <p class="hint">CAD 文件需下载后用专业软件查看</p>
      <div class="cad-tips">
        <el-tag size="small" type="info">AutoCAD</el-tag>
        <el-tag size="small" type="info">浩辰CAD</el-tag>
        <el-tag size="small" type="info">中望CAD</el-tag>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.file-preview-card { margin-bottom: 16px; }
.card-header { display: flex; align-items: center; gap: 6px; }
.file-info {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 12px; font-size: 13px; color: #606266;
}
.file-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.preview-area { border-radius: 8px; overflow: hidden; background: #f5f7fa; }
.preview-image { width: 100%; max-height: 300px; display: block; }
.preview-loading, .preview-error {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 8px; padding: 40px;
  color: #c0c4cc; font-size: 13px;
}
.preview-placeholder {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 8px; padding: 32px;
  background: #f5f7fa; border-radius: 8px; text-align: center;
}
.preview-placeholder p { color: #606266; margin: 0; font-size: 14px; }
.preview-placeholder .hint { color: #c0c4cc; font-size: 12px; }
.cad-tips { display: flex; gap: 6px; margin-top: 4px; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 1s linear infinite; }
</style>
