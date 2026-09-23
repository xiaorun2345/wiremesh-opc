<template>
  <div class="standards-search">
    <el-card>
      <template #header>
        <h2>国标条文检索</h2>
      </template>

      <!-- 搜索框 -->
      <div class="search-box">
        <el-input
          v-model="query"
          placeholder="输入问题，如：建筑防护网丝径要求、热镀锌层标准..."
          size="large"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button :icon="Search" @click="handleSearch" :loading="searching">
              检索
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- 检索结果 -->
      <div v-if="results.length > 0" class="results">
        <h3>找到 {{ results.length }} 条相关条文</h3>
        <el-card
          v-for="(result, idx) in results"
          :key="idx"
          class="result-card"
          shadow="hover"
        >
          <div class="result-header">
            <span class="result-title">
              {{ result.standard_name }} {{ result.section }}
            </span>
            <div class="result-badges">
              <el-tag
                v-if="result.is_mandatory"
                type="danger"
                size="small"
                class="mr-1"
              >
                强制性
              </el-tag>
              <el-tag type="success" size="small">
                匹配度 {{ (result.score * 100).toFixed(1) }}%
              </el-tag>
            </div>
          </div>

          <div v-if="result.chapter" class="result-chapter">
            所属章节：{{ result.chapter }}
          </div>

          <div class="result-content">
            {{ result.content }}
          </div>

          <div v-if="result.keywords.length > 0" class="result-keywords">
            <el-tag
              v-for="kw in result.keywords"
              :key="kw"
              size="small"
              type="info"
              class="mr-1"
            >
              {{ kw }}
            </el-tag>
          </div>
        </el-card>
      </div>

      <!-- 无结果 -->
      <el-empty
        v-else-if="searched"
        description="未找到相关条文，请尝试其他关键词"
      />

      <!-- 初始状态提示 -->
      <el-empty
        v-else
        description="输入问题开始检索国标条文"
      >
        <template #image>
          <el-icon :size="100" color="#909399">
            <Search />
          </el-icon>
        </template>
        <template #description>
          <p class="hint-text">试试搜索：</p>
          <div class="hint-buttons">
            <el-button size="small" @click="quickSearch('建筑防护网丝径和网孔要求')">
              防护网标准
            </el-button>
            <el-button size="small" @click="quickSearch('电气漏电保护标准')">
              电气漏电保护
            </el-button>
            <el-button size="small" @click="quickSearch('室内空气质量甲醛限值')">
              室内空气质量
            </el-button>
          </div>
        </template>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { queryStandards, type QueryResult } from '@/api/standards'

const query = ref('')
const results = ref<QueryResult[]>([])
const searching = ref(false)
const searched = ref(false)

async function handleSearch() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入检索内容')
    return
  }

  searching.value = true
  searched.value = true

  try {
    const data = await queryStandards(query.value, 8)
    results.value = data.results
  } catch (e) {
    ElMessage.error('检索失败，请检查网络或稍后重试')
    results.value = []
  } finally {
    searching.value = false
  }
}

function quickSearch(text: string) {
  query.value = text
  handleSearch()
}
</script>

<style scoped>
.standards-search {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}
.search-box {
  margin-bottom: 24px;
}
.results h3 {
  margin: 0 0 16px;
  color: #303133;
  font-size: 16px;
}
.result-card {
  margin-bottom: 12px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.result-title {
  font-weight: bold;
  font-size: 15px;
  color: #2B5E3B;
}
.result-badges {
  display: flex;
  gap: 4px;
}
.mr-1 {
  margin-right: 4px;
}
.result-chapter {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
.result-content {
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
  margin-bottom: 8px;
}
.result-keywords {
  display: flex;
  flex-wrap: wrap;
}
.hint-text {
  color: #909399;
  margin-bottom: 8px;
}
.hint-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
}
</style>
