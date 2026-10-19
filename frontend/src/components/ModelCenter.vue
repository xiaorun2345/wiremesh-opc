<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { opcApi } from '@/api/opc'

type Provider = { id:string; provider:string; purpose:string; model:string; base_url:string; api_key_status:string; enabled:boolean }
const providers = ref<Provider[]>([])
const saving = ref(false)
const presets: Record<string, { model:string; url:string; label:string }> = {
  qwen:{ label:'千问 Qwen', model:'qwen-plus', url:'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  openai:{ label:'OpenAI / ChatGPT', model:'gpt-4.1-mini', url:'https://api.openai.com/v1' },
  deepseek:{ label:'DeepSeek', model:'deepseek-chat', url:'https://api.deepseek.com' },
  zhipu:{ label:'智谱 GLM', model:'glm-4.7', url:'https://open.bigmodel.cn/api/paas/v4' },
  custom:{ label:'自定义兼容接口', model:'', url:'' },
}
const form = reactive({ provider:'qwen', purpose:'text', model:'qwen-plus', base_url:presets.qwen.url, api_key:'', enabled:true })
function applyPreset() { const item=presets[form.provider]; form.model=item.model; form.base_url=item.url }
async function load() { if (import.meta.env.VITE_USE_MOCK === 'true') return; providers.value=(await opcApi.listModelProviders()).data }
async function save() {
  if (!form.api_key) return ElMessage.warning('请输入 API Key；保存后只显示掩码')
  saving.value=true
  try { await opcApi.createModelProvider({ ...form }); form.api_key=''; await load(); ElMessage.success('模型已加密保存，可用于翻译与工作流') } finally { saving.value=false }
}
async function toggle(item:Provider) { await opcApi.updateModelProvider(item.id,{...item,api_key:'',enabled:!item.enabled}); await load() }
async function remove(item:Provider) { if (!import.meta.env.VITE_USE_MOCK) await opcApi.deleteModelProvider(item.id); providers.value=providers.value.filter(x=>x.id!==item.id) }
onMounted(load)
</script>

<template><section class="model-center">
  <header><div><span>MODEL ROUTING</span><h3>模型中心</h3><p>每个 Key 均加密保存，页面不会再次展示；文本模型用于翻译、商机整理、客服和工作流决策。</p></div></header>
  <div class="layout"><article class="card"><h4>添加模型</h4><el-form label-position="top"><el-form-item label="模型供应商"><el-select v-model="form.provider" @change="applyPreset"><el-option v-for="(item,key) in presets" :key="key" :label="item.label" :value="key"/></el-select></el-form-item><el-form-item label="用途"><el-radio-group v-model="form.purpose"><el-radio-button label="text">文本/翻译/客服</el-radio-button><el-radio-button label="vision">识图</el-radio-button></el-radio-group></el-form-item><el-form-item label="模型名称"><el-input v-model="form.model" placeholder="例如 qwen-plus"/></el-form-item><el-form-item label="兼容接口地址"><el-input v-model="form.base_url" placeholder="https://.../v1"/></el-form-item><el-form-item label="API Key"><el-input v-model="form.api_key" type="password" show-password autocomplete="off" placeholder="仅传至本机服务端并加密保存"/></el-form-item><el-button type="primary" :loading="saving" @click="save">加密保存并启用</el-button></el-form></article>
  <article class="card"><h4>已配置模型</h4><div v-if="!providers.length" class="empty">尚未配置。可先添加千问、DeepSeek 或 OpenAI。</div><div v-for="item in providers" :key="item.id" class="provider"><div><b>{{ presets[item.provider]?.label || item.provider }} · {{ item.model }}</b><small>{{ item.purpose==='vision'?'识图':'文本工作流' }} · {{ item.api_key_status }}</small></div><div><el-tag :type="item.enabled?'success':'info'">{{ item.enabled?'启用':'停用' }}</el-tag><el-button text @click="toggle(item)">{{ item.enabled?'停用':'启用' }}</el-button><el-button text type="danger" @click="remove(item)">删除</el-button></div></div></article></div>
</section></template>

<style scoped>
.model-center header span{font-size:10px;color:#6685aa;font-weight:800;letter-spacing:1px}.model-center h3{margin:4px 0;font-size:23px}.model-center header p{color:#8290a2;font-size:12px}.layout{display:grid;grid-template-columns:minmax(320px,.9fr) minmax(360px,1.1fr);gap:16px}.card{background:#fff;border:1px solid #e2eaf2;border-radius:12px;padding:20px}.card h4{margin:0 0 14px}.provider{display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px solid #edf1f5;padding:14px 0}.provider b,.provider small{display:block}.provider b{font-size:13px}.provider small{color:#8290a2;margin-top:5px}.empty{color:#8290a2;font-size:13px;padding:28px 0}@media(max-width:850px){.layout{grid-template-columns:1fr}}
</style>
