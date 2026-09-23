<template>
  <div class="standards-admin">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>国标标准文档管理</h2>
          <el-upload
            :show-file-list="false"
            :before-upload="handleUpload"
            accept=".pdf"
          >
            <el-button type="primary" :icon="Upload">
              上传 PDF 标准
            </el-button>
          </el-upload>
        </div>
      </template>

      <!-- 上传进度 -->
      <el-alert
        v-if="uploading"
        :title="uploadStatus"
        type="info"
        :closable="false"
        show-icon
        class="mb-4"
      />

      <!-- 标准列表 -->
      <el-table :data="standards" stripe v-loading="loading">
        <el-table-column prop="standard_name" label="标准号" width="200" />
        <el-table-column prop="filename" label="文件名" min-width="250" />
        <el-table-column prop="section_count" label="条文数" width="100" align="right" />
        <el-table-column prop="categories" label="分类" width="150">
          <template #default="{ row }">
            <el-tag
              v-for="cat in row.categories"
              :key="cat"
              size="small"
              class="mr-1"
            >
              {{ categoryLabel(cat) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              size="small"
              @click="handleDelete(row)"
              :disabled="row.status === 'extracting'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="total-info">
        共 {{ total }} 个标准文档
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  uploadStandard,
  listStandards,
  deleteStandard,
  type StandardInfo,
} from '@/api/standards'

const standards = ref<StandardInfo[]>([])
const total = ref(0)
const loading = ref(false)
const uploading = ref(false)
const uploadStatus = ref('')

const categoryMap: Record<string, string> = {
  waterproof: '防水',
  electrical: '电气',
  plumbing: '给排水',
  fire_safety: '防火',
  environment: '环保',
  quality_accept: '质量验收',
  general: '通用',
}

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  extracting: { label: '提取中', type: 'warning' },
  imported: { label: '已导入', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

function categoryLabel(cat: string) {
  return categoryMap[cat] || cat
}

function statusLabel(status: string) {
  return statusMap[status]?.label || status
}

function statusType(status: string) {
  return statusMap[status]?.type || 'info'
}

async function fetchStandards() {
  loading.value = true
  try {
    const data = await listStandards()
    standards.value = data.standards
    total.value = data.total
  } catch (e) {
    ElMessage.error('加载标准列表失败')
  } finally {
    loading.value = false
  }
}

async function handleUpload(file: File) {
  uploading.value = true
  uploadStatus.value = `正在上传 ${file.name}...`

  try {
    const data = await uploadStandard(file)
    uploadStatus.value = data.message
    ElMessage.success(data.message)
    // 轮询状态
    pollStatus(file.name)
  } catch (e: any) {
    uploadStatus.value = '上传失败'
    ElMessage.error(e.response?.data?.detail?.message || '上传失败')
  } finally {
    uploading.value = false
  }
  return false // 阻止自动上传
}

async function pollStatus(filename: string) {
  // 简单轮询，检查导入状态
  const maxAttempts = 60
  let attempts = 0
  const interval = setInterval(async () => {
    attempts++
    try {
      await fetchStandards()
      const item = standards.value.find(s => s.filename === filename)
      if (item && item.status !== 'extracting') {
        clearInterval(interval)
        if (item.status === 'imported') {
          ElMessage.success(`条文提取完成，共 ${item.section_count} 条`)
        }
      }
    } catch {
      // ignore
    }
    if (attempts >= maxAttempts) {
      clearInterval(interval)
    }
  }, 5000)
}

async function handleDelete(row: StandardInfo) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.standard_name} 吗？（ChromaDB 中的条文需要手动清理）`,
      '确认删除',
      { type: 'warning' }
    )
    await deleteStandard(row.filename)
    ElMessage.success('删除成功')
    await fetchStandards()
  } catch {
    // cancelled
  }
}

onMounted(fetchStandards)
</script>

<style scoped>
.standards-admin {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header h2 {
  margin: 0;
  font-size: 18px;
}
.mb-4 {
  margin-bottom: 16px;
}
.mr-1 {
  margin-right: 4px;
}
.total-info {
  margin-top: 16px;
  color: #909399;
  font-size: 14px;
}
</style>
