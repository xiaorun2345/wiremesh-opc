<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()

const mode    = ref<'login' | 'register'>('login')
const loading = ref(false)
const form    = reactive({ username: '', password: '', confirmPassword: '' })

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (mode.value === 'register' && form.password !== form.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.username, form.password)
    } else {
      await auth.register(form.username, form.password)
    }
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
    ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="logo">
        <el-icon size="40" color="#409eff"><House /></el-icon>
        <h1>丝网 OPC</h1>
        <p>AI 询盘、报价与交付工作台</p>
      </div>

      <el-tabs v-model="mode" class="tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-alert
        v-if="mode === 'login'"
        title="首次使用本地部署，请先切换到“注册”创建账号。"
        type="info"
        :closable="false"
        class="first-use-tip"
      />

      <el-form @submit.prevent="submit" class="form">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="'User'"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="'Lock'"
          />
        </el-form-item>
        <el-form-item v-if="mode === 'register'">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
            :prefix-icon="'Lock'"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          native-type="submit"
          :loading="loading"
          style="width: 100%"
        >
          {{ mode === 'login' ? '登录' : '注册' }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 380px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.logo {
  text-align: center;
  margin-bottom: 24px;
}
.logo h1 {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 8px 0 4px;
}
.logo p {
  color: #909399;
  font-size: 13px;
}
.tabs { margin-bottom: 20px; }
.first-use-tip { margin: -8px 0 16px; }
.form .el-form-item { margin-bottom: 16px; }
</style>
