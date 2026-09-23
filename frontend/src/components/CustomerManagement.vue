<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { opcApi } from '@/api/opc'

type Customer = {
  id: string; initials: string; name: string; region: string; language: string;
  level: string; source: string; contact_name: string; contact_channel: string;
  notes: string; rfq: number; revenue: string; next: string;
}

const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const search = ref('')
const levelFilter = ref('')
const dialog = ref(false)
const editingId = ref('')
const followupDialog = ref(false)
const selected = ref<Customer | null>(null)
const customers = ref<Customer[]>([
  { id:'c1', initials:'河', name:'河北安筑工程有限公司', region:'中国 · 河北', language:'zh-CN', level:'A', source:'企业微信', contact_name:'王经理', contact_channel:'wecom:wang', notes:'建筑防护网长期客户，重视交期。', rfq:12, revenue:'¥286,000', next:'今天 16:00' },
  { id:'c2', initials:'NF', name:'Nordic Fence AB', region:'瑞典 · 哥德堡', language:'en', level:'A', source:'独立站', contact_name:'Erik', contact_channel:'erik@example.com', notes:'需要 CE 资料和英文包装。', rfq:8, revenue:'$41,600', next:'明天' },
  { id:'c3', initials:'海', name:'山东海岳矿业', region:'中国 · 山东', language:'zh-CN', level:'B', source:'转介绍', contact_name:'赵工', contact_channel:'138****8801', notes:'工业筛网，重点关注材质报告。', rfq:5, revenue:'¥198,000', next:'09-25' },
])
const form = reactive({ name:'', region:'', language:'zh-CN', level:'B', source:'manual', contact_name:'', contact_channel:'', notes:'', next:'' })
const followup = reactive({ type:'电话', content:'', next:'' })

const filtered = computed(() => customers.value.filter(item => {
  const keyword = search.value.toLowerCase()
  const matches = !keyword || `${item.name}${item.region}${item.contact_name}${item.source}`.toLowerCase().includes(keyword)
  return matches && (!levelFilter.value || item.level === levelFilter.value)
}))

onMounted(async () => {
  if (useMock) return
  try {
    const { data } = await opcApi.listCustomers()
    customers.value = data.map((x: any) => ({ ...x, initials:x.name.slice(0,2), rfq:0, revenue:'—', next:'未安排' }))
  } catch { ElMessage.warning('客户数据加载失败，已保留本地演示数据') }
})

function resetForm() { Object.assign(form, { name:'', region:'', language:'zh-CN', level:'B', source:'manual', contact_name:'', contact_channel:'', notes:'', next:'' }) }
function openCreate() { editingId.value=''; resetForm(); dialog.value=true }
function openEdit(item: Customer) { editingId.value=item.id; Object.assign(form, item); dialog.value=true }

async function save() {
  if (!form.name.trim()) return ElMessage.warning('请填写客户名称')
  const payload = { name:form.name, region:form.region, language:form.language, level:form.level, source:form.source, contact_name:form.contact_name, contact_channel:form.contact_channel, notes:form.notes }
  if (editingId.value) {
    if (!useMock) await opcApi.updateCustomer(editingId.value, payload)
    const item = customers.value.find(x => x.id === editingId.value)
    if (item) Object.assign(item, form, { initials:form.name.slice(0,2) })
  } else {
    const id = useMock ? `c-${Date.now()}` : (await opcApi.createCustomer(payload)).data.id
    customers.value.unshift({ id, initials:form.name.slice(0,2), ...form, rfq:0, revenue:'¥0' })
  }
  dialog.value=false; ElMessage.success('客户资料已保存')
}

async function remove(item: Customer) {
  await ElMessageBox.confirm(`确认删除客户“${item.name}”？`, '删除客户', { type:'warning' })
  if (!useMock) await opcApi.deleteCustomer(item.id)
  customers.value = customers.value.filter(x => x.id !== item.id)
  ElMessage.success('客户已删除')
}

function openFollowup(item: Customer) { selected.value=item; Object.assign(followup,{type:'电话',content:'',next:item.next}); followupDialog.value=true }
async function saveFollowup() { if (!followup.content.trim()) return ElMessage.warning('请填写跟进内容'); if(selected.value){const nextAt=/^\d{4}-\d{2}-\d{2}/.test(followup.next)?`${followup.next.slice(0,10)}T09:00:00`:null;if(!useMock)await opcApi.createFollowup({customer_id:selected.value.id,channel:followup.type,content:followup.content,next_at:nextAt});selected.value.next=followup.next||'待安排'} followupDialog.value=false; ElMessage.success('跟进记录已保存') }

defineExpose({ openCreate })
</script>

<template>
  <div>
    <div class="crm-summary"><article><span>客户总数</span><strong>{{ customers.length }}</strong><em>本月新增 4</em></article><article><span>A 级客户</span><strong>{{ customers.filter(x=>x.level==='A').length }}</strong><em>重点维护</em></article><article><span>待跟进</span><strong>6</strong><em>今日 3 项</em></article><article><span>复购客户</span><strong>68%</strong><em>近 90 天</em></article></div>
    <section class="card">
      <header><h3>客户列表</h3><div><el-input v-model="search" placeholder="搜索客户、联系人或地区" :prefix-icon="'Search'" clearable/><el-select v-model="levelFilter" placeholder="全部等级" clearable><el-option label="A级" value="A"/><el-option label="B级" value="B"/><el-option label="C级" value="C"/></el-select><el-button type="primary" @click="openCreate"><el-icon><Plus/></el-icon>新增客户</el-button></div></header>
      <div class="table"><div class="row head"><span>客户</span><span>等级</span><span>来源</span><span>历史询盘</span><span>累计成交</span><span>下次跟进</span><span>操作</span></div><div v-for="item in filtered" :key="item.id" class="row"><div class="customer"><i>{{ item.initials }}</i><span><b>{{ item.name }}</b><small>{{ item.region }} · {{ item.contact_name || '暂无联系人' }}</small></span></div><b class="level">{{ item.level }}</b><span>{{ item.source }}</span><span>{{ item.rfq }} 次</span><strong>{{ item.revenue }}</strong><span>{{ item.next }}</span><div class="actions"><button @click="openFollowup(item)">跟进</button><button @click="openEdit(item)">编辑</button><button class="danger" @click="remove(item)">删除</button></div></div></div>
    </section>

    <el-dialog v-model="dialog" :title="editingId ? '编辑客户' : '新增客户'" width="620px">
      <el-form label-position="top"><div class="form-grid"><el-form-item label="客户名称"><el-input v-model="form.name"/></el-form-item><el-form-item label="国家/地区"><el-input v-model="form.region"/></el-form-item><el-form-item label="客户等级"><el-select v-model="form.level"><el-option label="A级" value="A"/><el-option label="B级" value="B"/><el-option label="C级" value="C"/></el-select></el-form-item><el-form-item label="来源"><el-select v-model="form.source"><el-option label="企业微信" value="企业微信"/><el-option label="独立站" value="独立站"/><el-option label="邮件" value="邮件"/><el-option label="转介绍" value="转介绍"/><el-option label="手工录入" value="manual"/></el-select></el-form-item><el-form-item label="联系人"><el-input v-model="form.contact_name"/></el-form-item><el-form-item label="联系方式"><el-input v-model="form.contact_channel"/></el-form-item><el-form-item label="语言"><el-input v-model="form.language"/></el-form-item><el-form-item label="下次跟进"><el-input v-model="form.next" placeholder="例如：明天 10:00"/></el-form-item></div><el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="3"/></el-form-item></el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="followupDialog" title="新增跟进记录" width="520px"><el-form label-position="top"><el-form-item label="跟进方式"><el-select v-model="followup.type"><el-option label="电话" value="电话"/><el-option label="企业微信" value="企业微信"/><el-option label="邮件" value="邮件"/><el-option label="视频会议" value="视频会议"/></el-select></el-form-item><el-form-item label="沟通内容"><el-input v-model="followup.content" type="textarea" :rows="4"/></el-form-item><el-form-item label="下次跟进"><el-input v-model="followup.next"/></el-form-item></el-form><template #footer><el-button @click="followupDialog=false">取消</el-button><el-button type="primary" @click="saveFollowup">保存记录</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.crm-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}.crm-summary article,.card{background:#fff;border:1px solid #e2eaf2;border-radius:12px;box-shadow:0 5px 18px rgba(23,47,79,.045)}.crm-summary article{padding:17px}.crm-summary span,.crm-summary em{display:block;color:#8593a5;font-size:10px}.crm-summary strong{display:block;font-size:23px;margin:5px 0;color:#1f3148}.crm-summary em{font-style:normal;color:#24a57f}.card{padding:18px}.card header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.card h3{margin:0;font-size:16px}.card header>div{display:flex;gap:8px}.card header .el-input{width:240px}.card header .el-select{width:110px}.row{display:grid;grid-template-columns:1.7fr .35fr .65fr .65fr .8fr .7fr 1fr;gap:12px;align-items:center;min-height:58px;border-top:1px solid #edf1f5;color:#596b80;font-size:10px}.row.head{min-height:34px;border:0;color:#95a0ae;font-size:9px}.customer{display:flex;align-items:center;gap:9px}.customer>i{width:34px;height:34px;display:grid;place-items:center;border-radius:8px;background:#e9f2ff;color:#286dcc;font-style:normal;font-weight:700}.customer b,.customer small{display:block}.customer small{color:#96a2b0;margin-top:3px}.level{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;background:#23a984;color:#fff}.actions{display:flex;gap:4px}.actions button{border:0;background:#edf4ff;color:#286ed0;border-radius:5px;padding:5px 7px;font-size:8px;cursor:pointer}.actions .danger{background:#fff0ef;color:#d65b4c}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}.form-grid .el-select{width:100%}@media(max-width:900px){.crm-summary{grid-template-columns:1fr 1fr}.table{overflow:auto}.row{min-width:850px}}@media(max-width:600px){.crm-summary,.form-grid{grid-template-columns:1fr}.card header{align-items:flex-start;gap:10px;flex-direction:column}}
</style>
