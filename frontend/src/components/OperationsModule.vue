<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { quoteApi } from '@/api/quotes'
import CustomerManagement from './CustomerManagement.vue'
import FactoryManagement from './FactoryManagement.vue'
import OrderDelivery from './OrderDelivery.vue'
import InquiryManagement from './InquiryManagement.vue'
import KnowledgeManagement from './KnowledgeManagement.vue'
import PriceManagement from './PriceManagement.vue'

const props = defineProps<{ module: string }>()

const fileList = ref<UploadFile[]>([])
const parsing = ref(false)
const parsed = ref(false)
const quoteFilter = ref('全部')
const quoteDialog = ref(false)
const quoteDetailDialog = ref(false)
const calculating = ref(false)
const quoteResult = ref<any>(null)
const selectedQuote = ref<any>(null)
const customerModule = ref<InstanceType<typeof CustomerManagement> | null>(null)
const factoryModule = ref<InstanceType<typeof FactoryManagement> | null>(null)
const orderModule = ref<InstanceType<typeof OrderDelivery> | null>(null)
const inquiryModule = ref<InstanceType<typeof InquiryManagement> | null>(null)
const knowledgeModule = ref<InstanceType<typeof KnowledgeManagement> | null>(null)
const priceModule = ref<InstanceType<typeof PriceManagement> | null>(null)
const quoteForm = reactive({
  product_type: 'welded_mesh', material: 'low_carbon_steel',
  wire_diameter_mm: 3.5, mesh_size_mm: 50,
  width_m: 2, length_m: 3, quantity: 100,
  surface_treatment: 'hot_dip_galvanized', packaging: 'export',
  margin_rate: 0.15, freight: 800, currency: 'CNY',
})

const descriptions: Record<string, { eyebrow: string; title: string; desc: string; action: string }> = {
  询盘中心: { eyebrow: 'RFQ INBOX', title: '询盘中心', desc: '统一接收微信、邮件、网站和手工询盘，识别需求并推进到报价。', action: '新增询盘' },
  图纸识别: { eyebrow: 'DRAWING INTELLIGENCE', title: '图纸识别', desc: '识别 PDF、CAD 和图片中的丝网规格，低置信度字段交由人工确认。', action: '上传新图纸' },
  报价单: { eyebrow: 'QUOTATION CENTER', title: '报价单', desc: '管理草稿、待审批、已发送和已成交报价，完整追踪每次修改。', action: '新建报价' },
  订单交付: { eyebrow: 'ORDER DELIVERY', title: '订单交付', desc: '跟踪收款、工厂排产、生产、质检、装柜、物流和售后全过程。', action: '新建订单' },
  客户管理: { eyebrow: 'CUSTOMER CRM', title: '客户管理', desc: '统一沉淀客户来源、询盘历史、跟进记录、成交与复购信息。', action: '新增客户' },
  合作工厂: { eyebrow: 'FACTORY NETWORK', title: '合作工厂', desc: '按设备、工艺、质量、交期和历史表现匹配最适合的交付工厂。', action: '录入工厂' },
  知识库: { eyebrow: 'KNOWLEDGE BASE', title: '知识库', desc: '管理产品规格、材料价格、工艺标准、质检要求和历史问答。', action: '导入资料' },
  价格规则: { eyebrow: 'PRICING RULES', title: '价格规则', desc: '维护材料、加工、表面处理和包装价格，报价引擎自动读取生效版本。', action: '发布价格' },
  运营数据: { eyebrow: 'BUSINESS ANALYTICS', title: '运营数据', desc: '查看询盘转化、报价效率、产品结构和工厂履约表现。', action: '导出月报' },
}

const current = computed(() => descriptions[props.module] || descriptions.图纸识别)

type QuoteListItem = { id:string; customer:string; product:string; amount:string; margin:string; date:string; status:string; result?:any }
const quotes = ref<QuoteListItem[]>([
  { id: 'QT-20250922-006', customer: '河北安筑工程', product: '建筑防护网', amount: '¥58,600', margin: '13.5%', date: '今天 10:26', status: '待审批' },
  { id: 'QT-20250922-005', customer: 'Nordic Fence AB', product: '养殖围网', amount: '$12,840', margin: '16.2%', date: '今天 09:52', status: '草稿' },
  { id: 'QT-20250921-018', customer: '山东海岳矿业', product: '工业筛网', amount: '¥126,000', margin: '14.8%', date: '昨天', status: '已发送' },
  { id: 'QT-20250918-011', customer: 'Green Farm LLC', product: '六角网', amount: '$8,920', margin: '18.1%', date: '09-18', status: '已成交' },
])

const filteredQuotes = computed(() => quoteFilter.value === '全部' ? quotes.value : quotes.value.filter(item => item.status === quoteFilter.value))

function primaryAction() {
  if (props.module === '图纸识别') return ElMessage.info('请将文件拖入下方上传区')
  if (props.module === '报价单') {
    quoteResult.value = null
    quoteDialog.value = true
    return
  }
  if (props.module === '客户管理') return customerModule.value?.openCreate()
  if (props.module === '合作工厂') return factoryModule.value?.openCreate()
  if (props.module === '订单交付') return orderModule.value?.openCreate()
  if (props.module === '询盘中心') return inquiryModule.value?.openCreate()
  if (props.module === '知识库') return knowledgeModule.value?.openCreate()
  if (props.module === '价格规则') return priceModule.value?.openCreate()
  if (props.module === '运营数据') return exportAnalytics()
  ElMessage.success(`${current.value.action}功能已进入演示流程`)
}

function exportAnalytics() {
  const rows = [
    ['指标', '数值'], ['本月询盘', '108'], ['有效报价', '36'],
    ['成交金额', '486200'], ['平均响应分钟', '18'],
  ]
  const csv = `\uFEFF${rows.map(row => row.join(',')).join('\n')}`
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `丝网OPC运营月报-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('运营月报已导出')
}

function openQuoteFromInquiry(inquiry: any) {
  const specs = inquiry.specs || {}
  Object.assign(quoteForm, {
    product_type: inquiry.product_type || 'welded_mesh',
    material: specs.material || 'low_carbon_steel',
    wire_diameter_mm: specs.wire_diameter_mm || 3.5,
    mesh_size_mm: specs.mesh_size_mm || 50,
    width_m: specs.width_m || 2,
    length_m: specs.length_m || 3,
    quantity: specs.quantity || Math.max(1, Math.ceil((specs.quantity_area_m2 || 600) / 6)),
    surface_treatment: specs.surface_treatment || 'none',
  })
  quoteResult.value = null
  quoteDialog.value = true
}

async function calculateQuote() {
  calculating.value = true
  try {
    const { data } = await quoteApi.preview({ ...quoteForm })
    quoteResult.value = data
    ElMessage.success('确定性报价计算完成')
  } finally {
    calculating.value = false
  }
}

async function submitQuote() {
  if (!quoteResult.value) return
  await quoteApi.submit(quoteResult.value.quote_id)
  quotes.value.unshift({
    id: quoteResult.value.quote_id,
    customer: '询盘客户', product: quoteForm.product_type,
    amount: `${quoteResult.value.currency === 'CNY' ? '¥' : '$'}${quoteResult.value.quote_total.toLocaleString()}`,
    margin: `${Math.round(quoteResult.value.margin_rate * 1000) / 10}%`,
    date: '刚刚', status: '待审批', result: quoteResult.value,
  })
  ElMessage.success('报价已提交人工审批，企业微信通知将在后端配置后发送')
  quoteDialog.value = false
}

function openQuoteDetail(item: any) {
  selectedQuote.value = item
  quoteDetailDialog.value = true
}

async function decideQuote(item: any, decision: 'approve' | 'reject') {
  if (item.result?.quote_id) await quoteApi.decide(item.result.quote_id, decision)
  item.status = decision === 'approve' ? '已发送' : '草稿'
  ElMessage.success(decision === 'approve' ? '报价已批准并进入发送流程' : '报价已退回修改')
  quoteDetailDialog.value = false
}

async function downloadQuote(item: any, format: 'pdf' | 'excel') {
  if (!item.result?.quote_id) return ElMessage.warning('历史演示报价没有可下载文件')
  const response = await quoteApi.download(item.result.quote_id, format)
  const blob = response.data instanceof Blob ? response.data : new Blob([JSON.stringify(response.data)], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = `${item.id}.${format === 'pdf' ? 'pdf' : 'xlsx'}`; link.click(); URL.revokeObjectURL(url)
  ElMessage.success('报价文件已生成')
}

async function convertQuote(item: any) {
  if (!item.result?.quote_id) return ElMessage.warning('历史演示报价不能直接转订单')
  await quoteApi.convertOrder(item.result.quote_id)
  item.status = '已成交'
  quoteDetailDialog.value = false
  ElMessage.success('已生成订单并进入待排产状态')
}

async function startParsing() {
  if (!fileList.value.length) return ElMessage.warning('请先选择图纸文件')
  parsing.value = true
  await new Promise(resolve => setTimeout(resolve, 900))
  parsing.value = false
  parsed.value = true
  ElMessage.success('图纸识别完成，发现 2 个字段需要人工确认')
}

function confirmSpecs() { ElMessage.success('规格已确认，可以进入报价流程') }
</script>

<template>
  <section class="module-page">
    <header class="module-header">
      <div><span>{{ current.eyebrow }}</span><h2>{{ current.title }}</h2><p>{{ current.desc }}</p></div>
      <button @click="primaryAction"><el-icon><Plus /></el-icon>{{ current.action }}</button>
    </header>

    <template v-if="module === '图纸识别'">
      <div class="drawing-layout">
        <article class="module-card upload-card">
          <div class="card-title"><div><h3>上传客户图纸</h3><p>支持 PDF / DWG / DXF / JPG / PNG，最大 100MB</p></div><span>步骤 1/3</span></div>
          <el-upload v-model:file-list="fileList" drag :auto-upload="false" :limit="1" accept=".pdf,.dwg,.dxf,.jpg,.jpeg,.png" class="uploader">
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <p>拖拽图纸到这里，或 <b>点击选择文件</b></p><small>系统自动判断文件类型和最佳解析策略</small>
          </el-upload>
          <button class="wide-primary" :disabled="!fileList.length || parsing" @click="startParsing"><el-icon><MagicStick /></el-icon>{{ parsing ? '正在识别图纸...' : '开始 AI 识别' }}</button>
        </article>

        <article class="module-card recognition-card">
          <div class="card-title"><div><h3>识别结果</h3><p>AI 提取后由人工确认关键技术参数</p></div><span :class="parsed ? 'success' : ''">{{ parsed ? '识别完成' : '等待上传' }}</span></div>
          <div v-if="!parsed" class="empty-state"><el-icon><View /></el-icon><strong>等待图纸识别</strong><p>识别完成后，这里会展示原图、标注框和结构化规格。</p></div>
          <div v-else class="parsed-result">
            <div class="mini-drawing"><div></div><span>2 个低置信度字段</span></div>
            <dl>
              <div><dt>产品类型</dt><dd>建筑防护网 <em>98%</em></dd></div><div><dt>材质</dt><dd>低碳钢丝 <em>96%</em></dd></div>
              <div><dt>丝径</dt><dd>3.5 mm <em class="warn">74%</em></dd></div><div><dt>网孔</dt><dd>50 × 50 mm <em>94%</em></dd></div>
              <div><dt>尺寸</dt><dd>2.0 × 3.0 m <em class="warn">68%</em></dd></div><div><dt>表面处理</dt><dd>热镀锌 <em>91%</em></dd></div>
            </dl>
            <button class="wide-primary" @click="confirmSpecs"><el-icon><CircleCheck /></el-icon>确认规格并进入报价</button>
          </div>
        </article>
      </div>
    </template>

    <template v-else-if="module === '询盘中心'">
      <InquiryManagement ref="inquiryModule" @quote="openQuoteFromInquiry" />
    </template>

    <template v-else-if="module === '报价单'">
      <div class="summary-strip"><div><span>报价总额（本月）</span><strong>¥ 1,286,400</strong></div><div><span>平均响应时间</span><strong>18 分钟</strong></div><div><span>平均毛利率</span><strong>15.2%</strong></div><div><span>报价成交率</span><strong>33.3%</strong></div></div>
      <article class="module-card list-card">
        <div class="list-toolbar"><div class="tabs"><button v-for="item in ['全部','草稿','待审批','已发送','已成交']" :key="item" :class="{active:quoteFilter===item}" @click="quoteFilter=item">{{ item }}</button></div><div><el-input placeholder="搜索客户或报价编号" :prefix-icon="'Search'" /></div></div>
        <div class="data-table quote-table"><div class="data-row data-head"><span>报价编号</span><span>客户 / 产品</span><span>金额</span><span>毛利率</span><span>更新时间</span><span>状态</span><span>操作</span></div><div v-for="item in filteredQuotes" :key="item.id" class="data-row"><b>{{ item.id }}</b><span><strong>{{ item.customer }}</strong><small>{{ item.product }}</small></span><strong>{{ item.amount }}</strong><span>{{ item.margin }}</span><span>{{ item.date }}</span><em :class="item.status">{{ item.status }}</em><div class="quote-actions"><button @click="openQuoteDetail(item)">查看</button><button v-if="item.status==='待审批'" class="approve" @click="decideQuote(item,'approve')">批准</button><button v-if="item.status==='待审批'" class="reject" @click="decideQuote(item,'reject')">退回</button></div></div></div>
      </article>
    </template>

    <template v-else-if="module === '客户管理'">
      <CustomerManagement ref="customerModule" />
    </template>

    <template v-else-if="module === '订单交付'">
      <OrderDelivery ref="orderModule" />
    </template>

    <template v-else-if="module === '合作工厂'">
      <FactoryManagement ref="factoryModule" />
    </template>

    <template v-else-if="module === '知识库'">
      <KnowledgeManagement ref="knowledgeModule" />
    </template>

    <template v-else-if="module === '价格规则'">
      <PriceManagement ref="priceModule" />
    </template>

    <template v-else-if="module === '运营数据'">
      <div class="analytics-kpis"><article><span>本月询盘</span><strong>108</strong><em>↑ 18.7%</em></article><article><span>有效报价</span><strong>36</strong><em>↑ 12.5%</em></article><article><span>成交金额</span><strong>¥ 486,200</strong><em>↑ 22.1%</em></article><article><span>平均响应</span><strong>18m</strong><em>↓ 31.4%</em></article></div>
      <div class="analytics-grid"><article class="module-card chart-card"><div class="card-title"><div><h3>询盘与报价趋势</h3><p>最近 7 天</p></div><span class="legend"><i></i>询盘 <i></i>报价</span></div><div class="bar-chart"><div v-for="item in [{d:'周一',a:64,b:36},{d:'周二',a:82,b:48},{d:'周三',a:58,b:31},{d:'周四',a:91,b:56},{d:'周五',a:76,b:44},{d:'周六',a:48,b:24},{d:'周日',a:70,b:39}]" :key="item.d" class="bar-group"><div><i :style="{height:item.a+'%'}"></i><em :style="{height:item.b+'%'}"></em></div><span>{{ item.d }}</span></div></div></article><article class="module-card product-rank"><div class="card-title"><div><h3>热门产品</h3><p>按询盘数量</p></div></div><div v-for="(item,index) in [{n:'建筑防护网',v:32,p:100},{n:'养殖围网',v:24,p:75},{n:'工业筛网',v:19,p:59},{n:'护栏网',v:17,p:53},{n:'六角网',v:11,p:34}]" :key="item.n" class="rank-row"><b>{{ index+1 }}</b><span>{{ item.n }}<i><em :style="{width:item.p+'%'}"></em></i></span><strong>{{ item.v }}</strong></div></article></div>
    </template>

    <el-dialog v-model="quoteDialog" title="新建丝网报价" width="760px" class="quote-dialog">
      <div class="quote-form-grid">
        <el-form-item label="产品类型"><el-select v-model="quoteForm.product_type"><el-option label="焊接网" value="welded_mesh"/><el-option label="护栏网" value="fence_mesh"/><el-option label="六角网" value="hexagonal_mesh"/><el-option label="工业筛网" value="screen_mesh"/><el-option label="钢板网" value="expanded_mesh"/></el-select></el-form-item>
        <el-form-item label="材料"><el-select v-model="quoteForm.material"><el-option label="低碳钢丝" value="low_carbon_steel"/><el-option label="镀锌钢丝" value="galvanized_steel"/><el-option label="不锈钢 304" value="stainless_304"/><el-option label="不锈钢 316" value="stainless_316"/></el-select></el-form-item>
        <el-form-item label="丝径 mm"><el-input-number v-model="quoteForm.wire_diameter_mm" :min="0.1" :step="0.1"/></el-form-item>
        <el-form-item label="网孔 mm"><el-input-number v-model="quoteForm.mesh_size_mm" :min="1" :step="5"/></el-form-item>
        <el-form-item label="单片宽度 m"><el-input-number v-model="quoteForm.width_m" :min="0.1" :step="0.1"/></el-form-item>
        <el-form-item label="单片长度 m"><el-input-number v-model="quoteForm.length_m" :min="0.1" :step="0.5"/></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="quoteForm.quantity" :min="1" :step="10"/></el-form-item>
        <el-form-item label="表面处理"><el-select v-model="quoteForm.surface_treatment"><el-option label="无" value="none"/><el-option label="电镀锌" value="electro_galvanized"/><el-option label="热镀锌" value="hot_dip_galvanized"/><el-option label="浸塑" value="pvc_coated"/><el-option label="喷塑" value="powder_coated"/></el-select></el-form-item>
        <el-form-item label="包装"><el-select v-model="quoteForm.packaging"><el-option label="散装" value="bulk"/><el-option label="托盘" value="pallet"/><el-option label="出口包装" value="export"/></el-select></el-form-item>
        <el-form-item label="目标毛利"><el-input-number v-model="quoteForm.margin_rate" :min="0.05" :max="0.5" :step="0.01"/></el-form-item>
        <el-form-item label="预估运费"><el-input-number v-model="quoteForm.freight" :min="0" :step="100"/></el-form-item>
      </div>
      <div v-if="quoteResult" class="quote-result">
        <div><span>总面积</span><strong>{{ quoteResult.area_m2 }} m²</strong></div><div><span>理论重量</span><strong>{{ quoteResult.total_weight_kg }} kg</strong></div><div><span>成本合计</span><strong>¥ {{ quoteResult.costs.total }}</strong></div><div class="highlight"><span>建议报价</span><strong>¥ {{ quoteResult.quote_total }}</strong><small>¥ {{ quoteResult.unit_price_m2 }}/m²</small></div>
        <p>推荐工厂：{{ quoteResult.factory_matches?.[0]?.name || '暂无完整匹配' }} · 公式版本 {{ quoteResult.formula_version }}</p>
      </div>
      <template #footer><el-button @click="quoteDialog=false">取消</el-button><el-button type="primary" :loading="calculating" @click="calculateQuote">计算报价</el-button><el-button v-if="quoteResult" type="success" @click="submitQuote">提交人工审批</el-button></template>
    </el-dialog>
    <el-dialog v-model="quoteDetailDialog" title="报价详情与审批" width="680px">
      <div v-if="selectedQuote" class="quote-detail">
        <header><div><b>{{ selectedQuote.id }}</b><span>{{ selectedQuote.customer }} · {{ selectedQuote.product }}</span></div><em :class="selectedQuote.status">{{ selectedQuote.status }}</em></header>
        <div class="quote-detail-summary"><div><span>报价金额</span><strong>{{ selectedQuote.amount }}</strong></div><div><span>毛利率</span><strong>{{ selectedQuote.margin }}</strong></div><div><span>更新时间</span><strong>{{ selectedQuote.date }}</strong></div></div>
        <dl v-if="selectedQuote.result"><div><dt>总面积</dt><dd>{{ selectedQuote.result.area_m2 }} m²</dd></div><div><dt>理论重量</dt><dd>{{ selectedQuote.result.total_weight_kg }} kg</dd></div><div><dt>材料成本</dt><dd>{{ selectedQuote.result.costs.material }}</dd></div><div><dt>加工成本</dt><dd>{{ selectedQuote.result.costs.processing }}</dd></div><div><dt>表面处理</dt><dd>{{ selectedQuote.result.costs.surface }}</dd></div><div><dt>包装物流</dt><dd>{{ selectedQuote.result.costs.packaging + selectedQuote.result.costs.freight }}</dd></div></dl>
        <p v-else>历史报价演示数据尚未包含完整成本分解。</p>
      </div>
      <template #footer><el-button @click="quoteDetailDialog=false">关闭</el-button><el-button v-if="selectedQuote?.result" @click="downloadQuote(selectedQuote,'excel')">下载 Excel</el-button><el-button v-if="selectedQuote?.result" @click="downloadQuote(selectedQuote,'pdf')">下载 PDF</el-button><el-button v-if="selectedQuote?.status==='待审批'" type="danger" plain @click="decideQuote(selectedQuote,'reject')">退回修改</el-button><el-button v-if="selectedQuote?.status==='待审批'" type="success" @click="decideQuote(selectedQuote,'approve')">批准并发送</el-button><el-button v-if="selectedQuote?.status==='已发送'" type="primary" @click="convertQuote(selectedQuote)">转为订单</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.module-page { color:#1b2a40; }.module-header { display:flex; align-items:center; justify-content:space-between; margin:2px 0 20px; }.module-header span { color:#6685aa; font-size:10px; font-weight:800; letter-spacing:1.4px; }.module-header h2 { margin:3px 0 6px; font-size:24px; }.module-header p { color:#7f8da0; font-size:12px; }.module-header > button,.wide-primary { border:0; border-radius:8px; background:linear-gradient(90deg,#2676e9,#1c67d3); color:white; height:38px; padding:0 16px; display:flex; align-items:center; gap:7px; cursor:pointer; box-shadow:0 6px 14px rgba(38,118,233,.18); }.module-card { background:white; border:1px solid #e2eaf2; border-radius:12px; box-shadow:0 5px 18px rgba(23,47,79,.045); }.card-title { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:18px; }.card-title h3,.list-toolbar h3 { margin:0; font-size:16px; }.card-title p { color:#8b98a9; font-size:10px; margin-top:4px; }.card-title > span { color:#6e83a0; font-size:9px; background:#f1f5fa; padding:5px 8px; border-radius:10px; }.card-title > span.success { color:#168261; background:#e8f8f2; }
.drawing-layout { display:grid; grid-template-columns:.8fr 1.2fr; gap:18px; }.upload-card,.recognition-card { padding:20px; min-height:520px; }.uploader { margin-top:26px; }.upload-icon { font-size:46px; color:#8ea8c8; }.uploader p { font-size:13px; color:#4d617a; margin:10px 0 4px; }.uploader b { color:#2676e9; }.uploader small { color:#9ba6b4; font-size:10px; }.wide-primary { width:100%; justify-content:center; margin-top:18px; }.wide-primary:disabled { opacity:.45; cursor:not-allowed; }.empty-state { min-height:370px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#9ca8b7; }.empty-state .el-icon { font-size:54px; color:#c8d3df; }.empty-state strong { color:#667990; margin:14px 0 5px; }.empty-state p { font-size:11px; }.parsed-result { display:grid; grid-template-columns:180px 1fr; gap:14px; }.mini-drawing { height:250px; border-radius:8px; background:linear-gradient(145deg,#4a5f73,#152a3c); position:relative; overflow:hidden; }.mini-drawing div { position:absolute; inset:-30px; background-image:linear-gradient(rgba(214,226,234,.7) 2px,transparent 2px),linear-gradient(90deg,rgba(214,226,234,.7) 2px,transparent 2px); background-size:30px 30px; transform:perspective(420px) rotateX(58deg) rotateZ(-8deg) scale(1.4); }.mini-drawing span { position:absolute; left:10px; bottom:10px; color:#ffd38e; background:rgba(10,24,38,.8); padding:6px 8px; border-radius:5px; font-size:9px; }.parsed-result dl { margin:0; border:1px solid #e5ebf2; border-radius:8px; overflow:hidden; }.parsed-result dl div { display:grid; grid-template-columns:38% 1fr; border-bottom:1px solid #e8edf3; }.parsed-result dl div:last-child { border:0; }.parsed-result dt,.parsed-result dd { margin:0; padding:9px; font-size:10px; }.parsed-result dt { background:#f7f9fc; color:#7d8c9f; }.parsed-result dd { font-weight:600; }.parsed-result em { float:right; font-size:8px; color:#169878; font-style:normal; }.parsed-result em.warn { color:#dd7e23; }.parsed-result .wide-primary { grid-column:1/-1; }
.summary-strip,.factory-stats,.analytics-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }.summary-strip > div,.factory-stats > span,.analytics-kpis article { background:white; border:1px solid #e3eaf2; border-radius:10px; padding:17px; }.summary-strip span,.factory-stats span,.analytics-kpis span { color:#8492a4; font-size:10px; }.summary-strip strong,.factory-stats b,.analytics-kpis strong { display:block; font-size:20px; color:#1b2b42; margin-top:5px; }.list-card { padding:18px; }.list-toolbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:13px; }.tabs { display:flex; gap:5px; }.tabs button { border:0; background:#f3f6fa; color:#66778c; border-radius:6px; padding:7px 12px; font-size:10px; cursor:pointer; }.tabs button.active { background:#e8f1ff; color:#276fd3; font-weight:700; }.data-row { display:grid; align-items:center; min-height:53px; border-top:1px solid #edf1f5; color:#56687e; font-size:10px; gap:14px; }.data-head { min-height:34px; border:0; color:#95a0ae; font-size:9px; }.quote-table .data-row { grid-template-columns:1.15fr 1.35fr .8fr .55fr .7fr .55fr .4fr; }.data-row span strong,.data-row span small { display:block; }.data-row span small { color:#9aa5b2; margin-top:3px; }.data-row > em { width:fit-content; font-style:normal; padding:4px 7px; border-radius:10px; font-size:8px; }.data-row em.待审批 { color:#c1721c; background:#fff1db; }.data-row em.草稿 { color:#67798f; background:#eef2f6; }.data-row em.已发送 { color:#2b6fcf; background:#eaf2ff; }.data-row em.已成交 { color:#168261; background:#e7f8f1; }.data-row > button { border:0; background:transparent; color:#2871d5; cursor:pointer; font-size:9px; }
.crm-grid { display:grid; grid-template-columns:1.15fr .85fr; gap:18px; margin-bottom:18px; }.pipeline,.followup { padding:18px; }.funnel-row { display:grid; grid-template-columns:60px 1fr 28px; gap:10px; align-items:center; margin:12px 0; font-size:10px; }.funnel-row > div { height:8px; background:#edf2f7; border-radius:4px; overflow:hidden; }.funnel-row i { display:block; height:100%; background:linear-gradient(90deg,#2d7ae5,#24b49a); border-radius:4px; }.followup .card-title b { color:#2871d5; font-size:22px; }.followup > p { display:flex; align-items:center; gap:8px; padding:11px 0; border-top:1px solid #edf1f5; color:#52657b; font-size:10px; }.followup > p i { width:7px; height:7px; border-radius:50%; background:#5e92d7; }.followup > p i.high { background:#f08b3d; }.followup time { margin-left:auto; color:#9aa5b2; }.customer-table .data-row { grid-template-columns:1.6fr .35fr .65fr .65fr .8fr .65fr; }.customer-cell { display:flex; align-items:center; gap:9px; }.customer-cell > i { width:31px; height:31px; display:grid; place-items:center; border-radius:8px; background:#eaf2ff; color:#286dcc; font-style:normal; font-weight:700; }.level { width:23px; height:23px; display:grid; place-items:center; border-radius:50%; color:white; background:#22a882; }
.summary-strip strong.danger { color:#df674f; }.order-legend { display:flex; gap:12px; color:#8190a2; font-size:9px; }.order-legend i { display:inline-block; width:7px; height:7px; border-radius:2px; background:#327be1; margin-right:4px; }.order-legend span:last-child i { background:#22ad88; }.order-row { display:grid; grid-template-columns:1.35fr 1.2fr .65fr .55fr 1.2fr .65fr .3fr; gap:12px; align-items:center; min-height:66px; border-top:1px solid #edf1f5; font-size:9px; color:#586b81; }.order-row span,.order-row b { display:block; }.order-row b { color:#2f435c; margin-top:3px; }.order-id b { color:#2a6fcf; }.order-row > em { width:fit-content; font-style:normal; padding:4px 7px; border-radius:10px; background:#e8f7f2; color:#168463; }.order-row > em.尾款待收 { color:#c27420; background:#fff1dc; }.order-row > button { border:0; background:transparent; color:#2871d5; font-size:9px; cursor:pointer; }.progress-cell > i { display:block; height:6px; background:#edf2f6; border-radius:3px; overflow:hidden; margin-top:6px; }.progress-cell > i em { display:block; height:100%; border-radius:3px; background:linear-gradient(90deg,#307be3,#23b08c); }.delivery-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:18px; }.delivery-card { padding:17px; }.delivery-card h3 { margin:0 0 9px; font-size:14px; }.delivery-card p { display:grid; grid-template-columns:8px 1.1fr 1fr auto; gap:8px; align-items:center; min-height:39px; border-top:1px solid #edf1f5; font-size:9px; color:#62758b; }.delivery-card p i { width:7px; height:7px; border-radius:50%; background:#4888df; }.delivery-card p i.done { background:#20ad83; }.delivery-card p i.warn { background:#ee8b3e; }.delivery-card p b { color:#344a63; }.delivery-card time { color:#98a3b0; }
.factory-stats span { display:block; }.factory-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }.factory-card { padding:18px; }.factory-card-head { display:grid; grid-template-columns:42px 1fr auto; gap:10px; align-items:center; }.factory-avatar { width:42px; height:42px; display:grid; place-items:center; border-radius:10px; background:#e8f1ff; color:#2a6ecb; font-weight:800; }.factory-card h3 { font-size:13px; margin:0; }.factory-card p { color:#909daa; font-size:9px; margin:4px 0 0; }.factory-card-head > strong { color:#159877; font-size:17px; }.factory-card-head small { font-size:8px; }.capacity { display:flex; justify-content:space-between; margin:15px 0 10px; color:#8a97a7; font-size:8px; }.capacity i { display:inline-block; width:6px; height:6px; border-radius:50%; background:#24ba8e; margin-right:5px; }.factory-metrics { display:grid; grid-template-columns:repeat(3,1fr); background:#f7f9fc; border-radius:8px; padding:10px; }.factory-metrics div { text-align:center; border-right:1px solid #e4eaf1; }.factory-metrics div:last-child { border:0; }.factory-metrics span,.factory-metrics b { display:block; }.factory-metrics span { color:#8c99a8; font-size:8px; }.factory-metrics b { font-size:11px; margin-top:4px; }.tag-list { display:flex; gap:5px; flex-wrap:wrap; margin:12px 0; }.tag-list span { color:#63778e; background:#eef3f8; padding:4px 6px; border-radius:4px; font-size:8px; }.factory-card footer { display:flex; gap:7px; border-top:1px solid #edf1f5; padding-top:12px; }.factory-card footer button { flex:1; height:31px; border:1px solid #cfdae6; background:white; color:#52677f; border-radius:6px; font-size:9px; cursor:pointer; }.factory-card footer .match { background:#2875dc; border-color:#2875dc; color:white; }
.knowledge-layout { display:grid; grid-template-columns:230px 1fr; gap:18px; }.category-card { padding:17px; }.category-card h3 { margin:0 0 13px; font-size:15px; }.category-card > button { width:100%; height:38px; border:0; background:transparent; color:#687a90; border-radius:7px; display:flex; align-items:center; gap:8px; padding:0 9px; font-size:10px; cursor:pointer; }.category-card > button b { margin-left:auto; }.category-card > button.active { background:#eaf2ff; color:#286fd2; }.kb-health { border-top:1px solid #e8edf3; margin-top:14px; padding-top:15px; }.kb-health span,.kb-health strong { font-size:9px; }.kb-health strong { float:right; }.kb-health > i { display:block; height:6px; background:#edf2f6; border-radius:3px; margin:8px 0; overflow:hidden; }.kb-health > i em { display:block; width:92%; height:100%; background:#20ad84; }.kb-health small { color:#9aa5b2; font-size:8px; }.document-row { display:grid; grid-template-columns:38px 1fr auto 25px; gap:10px; align-items:center; min-height:59px; border-top:1px solid #edf1f5; }.doc-icon { width:34px; height:34px; display:grid; place-items:center; border-radius:8px; color:#2d73d4; background:#eaf2ff; }.document-row strong,.document-row span { display:block; }.document-row strong { font-size:10px; }.document-row span { color:#98a3b1; font-size:8px; margin-top:4px; }.document-row em { font-style:normal; font-size:8px; padding:4px 7px; border-radius:10px; }.document-row em.已生效 { color:#168261; background:#e7f8f1; }.document-row em.待复核 { color:#c1721c; background:#fff1db; }.document-row button { border:0; background:transparent; cursor:pointer; }
.analytics-kpis article em { display:block; color:#18936f; font-size:9px; font-style:normal; margin-top:7px; }.analytics-grid { display:grid; grid-template-columns:1.5fr .8fr; gap:18px; }.chart-card,.product-rank { padding:18px; }.legend { font-weight:400!important; letter-spacing:0!important; color:#8795a6!important; }.legend i { display:inline-block; width:7px; height:7px; border-radius:2px; background:#2e78df; margin:0 4px 0 8px; }.legend i:nth-child(2) { background:#25b395; }.bar-chart { height:260px; display:flex; align-items:flex-end; justify-content:space-around; border-bottom:1px solid #e4eaf1; padding:15px 10px 0; background:repeating-linear-gradient(to top,#eef2f6 0,#eef2f6 1px,transparent 1px,transparent 52px); }.bar-group { width:11%; text-align:center; }.bar-group > div { height:210px; display:flex; align-items:flex-end; justify-content:center; gap:4px; }.bar-group i,.bar-group em { width:13px; display:block; border-radius:4px 4px 0 0; background:#2f7be5; }.bar-group em { background:#24b495; }.bar-group span { display:block; font-size:8px; color:#8997a7; margin-top:9px; }.rank-row { display:grid; grid-template-columns:22px 1fr 24px; gap:9px; align-items:center; margin:15px 0; }.rank-row > b { width:21px; height:21px; display:grid; place-items:center; border-radius:6px; background:#edf3fa; color:#66809f; font-size:9px; }.rank-row > span { font-size:10px; }.rank-row > span i { display:block; height:5px; background:#edf2f6; border-radius:3px; margin-top:6px; overflow:hidden; }.rank-row > span i em { display:block; height:100%; background:linear-gradient(90deg,#2d78df,#24b394); }.rank-row > strong { font-size:10px; }
.quote-form-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:0 16px; }.quote-form-grid :deep(.el-form-item) { display:block; }.quote-form-grid :deep(.el-form-item__label) { display:block; text-align:left; color:#66788d; font-size:11px; }.quote-form-grid :deep(.el-select),.quote-form-grid :deep(.el-input-number) { width:100%; }.quote-result { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; background:#f3f7fb; border-radius:10px; padding:12px; margin-top:6px; }.quote-result > div { padding:8px; border-right:1px solid #dfe7ef; }.quote-result > div:last-of-type { border:0; }.quote-result span,.quote-result strong,.quote-result small { display:block; }.quote-result span { color:#7e8d9f; font-size:9px; }.quote-result strong { color:#233750; font-size:14px; margin-top:4px; }.quote-result .highlight strong { color:#0b9875; font-size:18px; }.quote-result small { color:#8190a1; font-size:8px; margin-top:2px; }.quote-result p { grid-column:1/-1; color:#5e728a; font-size:9px; border-top:1px solid #dfe7ef; padding-top:9px; margin:0; }
.quote-actions{display:flex;gap:3px}.quote-actions button{border:0;background:#edf4ff;color:#286ed0;border-radius:4px;padding:5px 6px;font-size:8px;cursor:pointer}.quote-actions .approve{background:#e6f7f1;color:#148161}.quote-actions .reject{background:#fff0ef;color:#d45a4c}.quote-detail header{display:flex;justify-content:space-between}.quote-detail header span{display:block;color:#8492a4;font-size:10px;margin-top:4px}.quote-detail header em{font-style:normal;padding:5px 9px;border-radius:12px;background:#eef3f8;color:#64778d;font-size:9px}.quote-detail header em.待审批{background:#fff1dc;color:#c0711d}.quote-detail-summary{display:grid;grid-template-columns:repeat(3,1fr);background:#f5f8fb;border-radius:9px;padding:12px;margin:18px 0}.quote-detail-summary div{text-align:center;border-right:1px solid #dfe6ed}.quote-detail-summary div:last-child{border:0}.quote-detail-summary span,.quote-detail-summary strong{display:block}.quote-detail-summary span{color:#8492a3;font-size:9px}.quote-detail-summary strong{margin-top:5px}.quote-detail dl{display:grid;grid-template-columns:1fr 1fr;border:1px solid #e3eaf1;border-radius:8px;overflow:hidden}.quote-detail dl div{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #e8edf3}.quote-detail dt,.quote-detail dd{padding:9px;margin:0;font-size:9px}.quote-detail dt{background:#f7f9fc;color:#77879a}.quote-detail p{background:#f6f8fb;padding:14px;border-radius:8px;color:#77869a;font-size:10px}
@media(max-width:1000px){.drawing-layout,.crm-grid,.knowledge-layout,.analytics-grid{grid-template-columns:1fr}.factory-grid{grid-template-columns:1fr 1fr}.summary-strip,.factory-stats,.analytics-kpis{grid-template-columns:1fr 1fr}}@media(max-width:700px){.module-header{align-items:flex-start;gap:12px}.module-header p{display:none}.drawing-layout,.factory-grid{grid-template-columns:1fr}.summary-strip,.factory-stats,.analytics-kpis{grid-template-columns:1fr}.data-table{overflow-x:auto}.data-row{min-width:760px}.parsed-result{grid-template-columns:1fr}.mini-drawing{height:170px}}
</style>
