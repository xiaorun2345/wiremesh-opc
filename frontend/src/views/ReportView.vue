<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reportsApi } from '@/api/reports'
import { ElMessage } from 'element-plus'
import type { ReportMeta } from '@/types'

const route  = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const meta     = ref<ReportMeta | null>(null)
const loading  = ref(false)
const dlLoading = ref<'pdf' | 'excel' | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await reportsApi.getMeta(taskId)
    meta.value = data
  } finally {
    loading.value = false
  }
})

async function download(format: 'pdf' | 'excel') {
  dlLoading.value = format
  try {
    await reportsApi.download(taskId, format)
    ElMessage.success(`${format.toUpperCase()} 报告下载成功`)
  } finally {
    dlLoading.value = null
  }
}
</script>

<template>
  <div class="report-page">
    <div class="report-card" v-loading="loading">
      <div class="back-btn">
        <el-button text @click="router.push(`/tasks/${taskId}`)">
          <el-icon><ArrowLeft /></el-icon> 返回任务详情
        </el-button>
      </div>

      <div class="header">
        <el-icon size="48" color="#67c23a"><CircleCheckFilled /></el-icon>
        <h2>算量报告已生成</h2>
        <p v-if="meta">生成时间：{{ new Date(meta.created_at).toLocaleString('zh-CN') }}</p>
      </div>

      <div class="download-options" v-if="meta">
        <el-card
          class="option-card"
          :class="{ disabled: !meta.pdf_available }"
          shadow="hover"
        >
          <el-icon size="40" color="#f56c6c"><Document /></el-icon>
          <h3>PDF 报告</h3>
          <p>包含工程量清单和合规审核结论</p>
          <el-button
            type="danger"
            size="large"
            :loading="dlLoading === 'pdf'"
            :disabled="!meta.pdf_available"
            @click="download('pdf')"
          >
            <el-icon><Download /></el-icon>
            下载 PDF
          </el-button>
        </el-card>

        <el-card
          class="option-card"
          :class="{ disabled: !meta.excel_available }"
          shadow="hover"
        >
          <el-icon size="40" color="#67c23a"><Grid /></el-icon>
          <h3>Excel 报告</h3>
          <p>结构化数据，方便二次处理</p>
          <el-button
            type="success"
            size="large"
            :loading="dlLoading === 'excel'"
            :disabled="!meta.excel_available"
            @click="download('excel')"
          >
            <el-icon><Download /></el-icon>
            下载 Excel
          </el-button>
        </el-card>
      </div>

      <div class="footer-actions">
        <el-button @click="router.push('/')">返回任务列表</el-button>
        <el-button type="primary" @click="router.push('/upload')">
          <el-icon><Upload /></el-icon> 上传新图纸
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.report-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 640px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.back-btn { margin-bottom: 16px; }
.header { text-align: center; margin-bottom: 32px; }
.header h2 { font-size: 24px; color: #303133; margin: 12px 0 8px; }
.header p { color: #909399; }
.download-options { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.option-card { text-align: center; padding: 8px; }
.option-card h3 { font-size: 16px; margin: 12px 0 6px; }
.option-card p { color: #909399; font-size: 13px; margin-bottom: 16px; }
.option-card.disabled { opacity: 0.5; }
.footer-actions { display: flex; justify-content: center; gap: 12px; }
</style>
