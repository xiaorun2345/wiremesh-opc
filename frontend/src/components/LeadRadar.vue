<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { opcApi } from '@/api/opc'

type Source = { id:string; name:string; provider:string; enabled:boolean; config:Record<string, unknown>; last_status:string; last_error:string; last_run_at?:string }
type Lead = { id:string; source:string; title:string; buyer:string; country:string; source_url:string; deadline_at?:string; score:number; status:string; score_reasons:string[]; extracted:Record<string, any>; created_at:string }
type Notice = { id:string; title:string; body:string; priority:string; read_at?:string; created_at:string; entity_id:string }
const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const tab = ref<'leads'|'sources'|'notifications'>('leads')
const loading = ref(false)
const sourceDialog = ref(false)
const tedConfig = { cpv_codes:['44313100','44313000','44313200','44312000','34928200','34928310'], keywords:['wire mesh','security fencing','mining screen'], countries:[], limit:50 }
const ukConfig = { url:'https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search', keywords:['wire mesh','welded mesh','security fencing','metal netting','wire cloth'], limit:100 }
const sourceForm = reactive({ name:'TED 欧盟采购', provider:'ted', enabled:true, configText:JSON.stringify(tedConfig, null, 2) })
const sources = ref<Source[]>([
  { id:'s1',name:'TED 欧盟采购（丝网）',provider:'ted',enabled:true,config:tedConfig,last_status:'READY',last_error:'' },
  { id:'s2',name:'英国 Contracts Finder（丝网）',provider:'contracts_finder',enabled:true,config:ukConfig,last_status:'READY',last_error:'' },
  { id:'s3',name:'SAM.gov 美国政府采购（待填免费 Key）',provider:'sam',enabled:false,config:{ api_key_env:'SAM_GOV_API_KEY',keyword:'wire mesh',lookback_days:2,limit:100,countries:['US'] },last_status:'NEEDS_FREE_KEY',last_error:'填写免费 SAM_GOV_API_KEY 后启用' },
])
const leads = ref<Lead[]>([
  {id:'l1',source:'ted',title:'Supply of anti-climb wire-mesh fencing',buyer:'Detention Service',country:'Malta',source_url:'https://ted.europa.eu/',deadline_at:'2026-11-06',score:89,status:'HIGH_PRIORITY',score_reasons:['匹配关键词：wire-mesh fencing、anti-climb','规格完整度：5/7','官方采购来源'],extracted:{spec:{product_type:'fence_mesh',material:'galvanized_steel',surface_treatment:'hot_dip_galvanized'}},created_at:'刚刚'},
  {id:'l2',source:'contracts_finder',title:'Security fencing and installation materials',buyer:'UK public sector buyer',country:'UK',source_url:'https://www.contractsfinder.service.gov.uk/',deadline_at:'2026-11-12',score:72,status:'NEW',score_reasons:['匹配关键词：security fencing','公告含预算','官方采购来源'],extracted:{spec:{product_type:'fence_mesh'}},created_at:'12分钟前'},
  {id:'l3',source:'rss',title:'Mining screen mesh procurement notice',buyer:'Mining Operator',country:'Australia',source_url:'',deadline_at:'2026-10-29',score:57,status:'NEW',score_reasons:['匹配关键词：mining screen','距截止日充足'],extracted:{spec:{product_type:'screen_mesh'}},created_at:'1小时前'},
])
const notifications = ref<Notice[]>([
  {id:'n1',title:'高优先级海外商机：Supply of anti-climb wire-mesh fencing',body:'来源：TED；国家：Malta；评分：89。',priority:'HIGH',entity_id:'l1',created_at:'刚刚'},
])
const statusFilter = ref('')
const filteredLeads = computed(() => leads.value.filter(item => !statusFilter.value || item.status === statusFilter.value))
const unread = computed(() => notifications.value.filter(item => !item.read_at).length)

const providers: Record<string,string> = { ted:'TED 欧盟采购', sam:'SAM.gov', contracts_finder:'Contracts Finder', rss:'公开 RSS' }

onMounted(load)
async function load() {
  if (useMock) return
  loading.value = true
  try {
    const [sourceRes, leadRes, noticeRes] = await Promise.all([opcApi.listLeadSources(), opcApi.listLeads(), opcApi.listNotifications()])
    sources.value = sourceRes.data
    if (!sources.value.length) {
      await opcApi.installDefaultLeadSources()
      sources.value = (await opcApi.listLeadSources()).data
    }
    leads.value = leadRes.data
    notifications.value = noticeRes.data
  } catch { ElMessage.warning('海外商机服务暂不可用，已展示本地示例') }
  finally { loading.value = false }
}
function openCreateSource() { Object.assign(sourceForm,{name:'TED 欧盟采购（丝网）',provider:'ted',enabled:true,configText:JSON.stringify(tedConfig, null, 2) }); sourceDialog.value=true }
async function saveSource() {
  let config:Record<string,unknown>
  try { config = JSON.parse(sourceForm.configText || '{}') } catch { return ElMessage.error('数据源配置 JSON 格式错误') }
  const payload = { name:sourceForm.name,provider:sourceForm.provider,enabled:sourceForm.enabled,config }
  const id = useMock ? `s-${Date.now()}` : (await opcApi.createLeadSource(payload)).data.id
  sources.value.unshift({id,...payload,last_status:'NEVER',last_error:''}); sourceDialog.value=false; ElMessage.success('数据源已保存')
}
async function runSource(source:Source) {
  if (useMock) { source.last_status='SUCCESS'; source.last_run_at='刚刚'; ElMessage.success('演示采集完成：新增 3 条、去重 1 条'); return }
  try { const {data} = await opcApi.runLeadSource(source.id); await load(); ElMessage.success(`采集完成：新增 ${data.created} 条，去重 ${data.duplicates} 条`) } catch (error:any) { ElMessage.error(error.response?.data?.detail || '采集失败，请检查数据源配置') }
}
async function ignoreLead(lead:Lead) { if (!useMock) await opcApi.updateLead(lead.id,{status:'IGNORED'}); lead.status='IGNORED'; ElMessage.success('已忽略该商机') }
async function convertLead(lead:Lead) { if (!useMock) await opcApi.convertLead(lead.id); lead.status='CONVERTED'; ElMessage.success('已转入询盘中心') }
async function readNotice(item:Notice) { if (!item.read_at && !useMock) await opcApi.readNotification(item.id); item.read_at=new Date().toISOString() }
async function removeSource(source:Source) { await ElMessageBox.confirm(`确认删除数据源“${source.name}”？`,'删除数据源',{type:'warning'}); if(!useMock) await opcApi.deleteLeadSource(source.id); sources.value=sources.value.filter(item=>item.id!==source.id) }
async function restoreFreeSources() { if (!useMock) { const {data} = await opcApi.installDefaultLeadSources(); await load(); ElMessage.success(data.created ? `已补齐 ${data.created} 个免费默认源` : '免费默认源已齐全') } }
defineExpose({ openCreateSource })
</script>

<template><div class="radar" v-loading="loading">
  <header class="hero"><div><span>OVERSEAS LEAD RADAR</span><h2>海外商机雷达</h2><p>仅采集官方 API、公开 RSS 或明确授权的数据源；高分商机自动进入询盘中心。</p></div><div class="hero-actions"><el-badge :value="unread" :hidden="!unread"><el-button @click="tab='notifications'">通知</el-button></el-badge><el-button type="primary" @click="openCreateSource"><el-icon><Plus/></el-icon>添加数据源</el-button></div></header>
  <div class="kpis"><article><span>高优先级</span><strong>{{ leads.filter(x=>x.status==='HIGH_PRIORITY').length }}</strong><em>即时提醒</em></article><article><span>今日新增</span><strong>{{ leads.length }}</strong><em>已自动去重</em></article><article><span>已转询盘</span><strong>{{ leads.filter(x=>x.status==='CONVERTED').length }}</strong><em>进入报价流程</em></article><article><span>运行中数据源</span><strong>{{ sources.filter(x=>x.enabled).length }}</strong><em>官方 API / RSS</em></article></div>
  <div class="tabs"><button :class="{active:tab==='leads'}" @click="tab='leads'">商机池</button><button :class="{active:tab==='sources'}" @click="tab='sources'">数据源</button><button :class="{active:tab==='notifications'}" @click="tab='notifications'">通知 {{ unread ? `(${unread})` : '' }}</button></div>
  <section v-if="tab==='leads'" class="card"><header><h3>海外采购商机</h3><el-select v-model="statusFilter" clearable placeholder="全部状态"><el-option label="高优先级" value="HIGH_PRIORITY"/><el-option label="待处理" value="NEW"/><el-option label="已转询盘" value="CONVERTED"/><el-option label="已忽略" value="IGNORED"/></el-select></header><div class="lead" v-for="lead in filteredLeads" :key="lead.id"><div class="score" :class="{hot:lead.score>=80}">{{ lead.score }}</div><div class="lead-main"><div><b>{{ lead.title }}</b><em :class="lead.status">{{ lead.status==='HIGH_PRIORITY'?'高优先级':lead.status==='CONVERTED'?'已转询盘':lead.status==='IGNORED'?'已忽略':'待处理' }}</em></div><span>{{ providers[lead.source] || lead.source }} · {{ lead.buyer || '买方待确认' }} · {{ lead.country || '国家待确认' }}</span><p>{{ lead.score_reasons.join(' · ') }}</p></div><div class="deadline"><span>截止日期</span><b>{{ lead.deadline_at?.slice(0,10) || '未识别' }}</b></div><div class="actions"><a v-if="lead.source_url" :href="lead.source_url" target="_blank">原始公告</a><button @click="convertLead(lead)" :disabled="lead.status==='CONVERTED'">转询盘</button><button class="ignore" @click="ignoreLead(lead)">忽略</button></div></div></section>
  <section v-else-if="tab==='sources'" class="card"><header><h3>采集数据源</h3><div class="source-actions"><el-button @click="restoreFreeSources">恢复免费默认源</el-button><el-button type="primary" @click="openCreateSource"><el-icon><Plus/></el-icon>添加数据源</el-button></div></header><div class="source" v-for="source in sources" :key="source.id"><div class="source-logo">{{ source.provider.toUpperCase().slice(0,3) }}</div><div><b>{{ source.name }}</b><span>{{ providers[source.provider] || source.provider }} · {{ source.enabled?'已启用':'已停用' }}</span><small>最近运行：{{ source.last_run_at || '从未运行' }} · {{ source.last_status }} {{ source.last_error ? `· ${source.last_error}` : '' }}</small></div><div class="actions"><button @click="runSource(source)" :disabled="!source.enabled">立即采集</button><button class="ignore" @click="removeSource(source)">删除</button></div></div></section>
  <section v-else class="card"><header><h3>提醒中心</h3><span>{{ unread }} 条未读</span></header><div class="notice" v-for="notice in notifications" :key="notice.id" :class="{read:notice.read_at}" @click="readNotice(notice)"><i :class="notice.priority"></i><div><b>{{ notice.title }}</b><p>{{ notice.body }}</p><small>{{ notice.created_at }}</small></div><span>{{ notice.read_at?'已读':'未读' }}</span></div><el-empty v-if="!notifications.length" description="暂无提醒" :image-size="70"/></section>
  <el-dialog v-model="sourceDialog" title="添加海外采购数据源" width="680px"><el-alert type="info" :closable="false" title="请仅使用官方 API、公开 RSS 或获得授权的公开数据源；不要填写需要网页登录、验证码或违反平台条款的抓取地址。"/><el-form label-position="top" class="source-form"><el-form-item label="名称"><el-input v-model="sourceForm.name"/></el-form-item><el-form-item label="数据源类型"><el-select v-model="sourceForm.provider"><el-option label="TED 欧盟公开采购 API" value="ted"/><el-option label="SAM.gov API（需 API Key）" value="sam"/><el-option label="英国 Contracts Finder OCDS API" value="contracts_finder"/><el-option label="公开 RSS Feed" value="rss"/></el-select></el-form-item><el-form-item label="启用"><el-switch v-model="sourceForm.enabled"/></el-form-item><el-form-item label="配置 JSON"><el-input v-model="sourceForm.configText" type="textarea" :rows="8"/><p class="hint">TED 可填写 CPV 代码、国家和关键词；SAM 可使用 <code>api_key_env: "SAM_GOV_API_KEY"</code>；RSS 必填 <code>feed_url</code>。</p></el-form-item></el-form><template #footer><el-button @click="sourceDialog=false">取消</el-button><el-button type="primary" @click="saveSource">保存数据源</el-button></template></el-dialog>
</div></template>

<style scoped>
.hero{display:flex;justify-content:space-between;align-items:center;margin:2px 0 18px}.hero span{color:#6685aa;font-size:10px;letter-spacing:1.4px;font-weight:800}.hero h2{margin:4px 0;font-size:24px}.hero p{margin:0;color:#8290a2;font-size:12px}.hero-actions{display:flex;gap:8px}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}.kpis article,.card{background:#fff;border:1px solid #e2eaf2;border-radius:12px;box-shadow:0 5px 18px rgba(23,47,79,.045)}.kpis article{padding:17px}.kpis span,.kpis em{display:block;color:#8492a4;font-size:9px}.kpis strong{display:block;font-size:23px;margin:5px 0;color:#203249}.kpis em{font-style:normal;color:#20a681}.tabs{display:flex;gap:7px;margin-bottom:12px}.tabs button{border:0;background:#eaf0f6;color:#62768d;padding:8px 14px;border-radius:7px;cursor:pointer;font-size:10px}.tabs button.active{background:#2d78dd;color:#fff}.card{padding:18px}.card>header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.card h3{margin:0;font-size:15px}.lead{display:grid;grid-template-columns:44px 1fr 95px 150px;gap:13px;align-items:center;min-height:83px;border-top:1px solid #edf1f5}.score{width:36px;height:36px;display:grid;place-items:center;border-radius:10px;background:#ebf2fc;color:#3975c3;font-weight:800}.score.hot{background:#fff0df;color:#d97724}.lead-main b{font-size:11px;color:#263b54}.lead-main em{font-style:normal;font-size:8px;padding:3px 6px;border-radius:8px;background:#edf2f6;margin-left:6px}.lead-main em.HIGH_PRIORITY{color:#be6c1b;background:#fff0dc}.lead-main em.CONVERTED{color:#168363;background:#e7f8f1}.lead-main span,.lead-main p{display:block;color:#8290a1;font-size:9px;margin:5px 0}.lead-main p{color:#4d708f}.deadline span,.deadline b{display:block;font-size:9px}.deadline span{color:#91a0af}.deadline b{margin-top:4px}.actions{display:flex;gap:5px;flex-wrap:wrap}.actions button,.actions a{border:0;background:#eaf3ff;color:#296fcd;border-radius:5px;padding:6px 7px;font-size:8px;cursor:pointer;text-decoration:none}.actions .ignore{background:#fff0ef;color:#d25b4d}.source{display:grid;grid-template-columns:44px 1fr 140px;gap:11px;align-items:center;min-height:70px;border-top:1px solid #edf1f5}.source-logo{width:38px;height:38px;display:grid;place-items:center;border-radius:9px;background:#eaf2ff;color:#2c70cf;font-size:9px;font-weight:800}.source b,.source span,.source small{display:block}.source b{font-size:11px}.source span,.source small{color:#8492a2;font-size:9px;margin-top:4px}.notice{display:grid;grid-template-columns:10px 1fr auto;gap:10px;padding:12px 0;border-top:1px solid #edf1f5;cursor:pointer}.notice.read{opacity:.55}.notice i{width:8px;height:8px;border-radius:50%;background:#4b89e3;margin-top:5px}.notice i.HIGH{background:#ef8b3e}.notice b{font-size:10px}.notice p,.notice small{margin:4px 0;color:#8190a1;font-size:9px}.notice>span{font-size:9px;color:#6380a0}.source-form{margin-top:15px}.source-form .el-select{width:100%}.hint{font-size:9px;color:#8290a2}.hint code{background:#f1f5f8;padding:2px 4px;border-radius:3px}@media(max-width:850px){.kpis{grid-template-columns:1fr 1fr}.lead{grid-template-columns:44px 1fr}.lead .deadline,.lead .actions{grid-column:2}.source{grid-template-columns:44px 1fr}.source .actions{grid-column:2}}@media(max-width:560px){.hero{align-items:flex-start;gap:10px;flex-direction:column}.kpis{grid-template-columns:1fr}.hero p{display:none}}
</style>
