<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import OperationsModule from '@/components/OperationsModule.vue'

const router = useRouter()
const auth = useAuthStore()
const activeMenu = ref('工作台')
const reviewStatus = ref<'pending' | 'approved' | 'editing'>('pending')

const menuItems = [
  { label: '工作台', icon: 'House' },
  { label: '海外商机', icon: 'Radar' },
  { label: '询盘中心', icon: 'ChatDotRound' }, { label: '图纸识别', icon: 'Picture' },
  { label: '报价单', icon: 'Document' }, { label: '订单交付', icon: 'Box' }, { label: '客户管理', icon: 'User' },
  { label: '合作工厂', icon: 'OfficeBuilding' }, { label: '知识库', icon: 'Collection' },
  { label: '价格规则', icon: 'Money' },
  { label: '运营数据', icon: 'DataLine' },
]

const metrics = [
  { label: '待确认询盘', value: '8', change: '+3', icon: 'ChatDotRound', tone: 'blue' },
  { label: '本月报价', value: '36', change: '+12.5%', icon: 'Tickets', tone: 'teal' },
  { label: '成交订单', value: '12', change: '+4', icon: 'CircleCheck', tone: 'orange' },
  { label: '合作工厂', value: '5', change: '稳定', icon: 'OfficeBuilding', tone: 'purple' },
]

const inquiries = [
  { id: 'INQ-20250922001', customer: '河北安筑工程', product: '建筑防护网', source: '企业微信', time: '10:24', status: '待确认' },
  { id: 'INQ-20250922002', customer: 'Nordic Fence AB', product: '养殖围网', source: '邮件', time: '09:48', status: '识别中' },
  { id: 'INQ-20250921018', customer: '山东海岳矿业', product: '工业筛网', source: '网站', time: '昨天', status: '已报价' },
]

const statusText = computed(() => reviewStatus.value === 'approved' ? '已确认并发送' : reviewStatus.value === 'editing' ? '等待修改' : '等待人工确认')

function chooseMenu(label: string) {
  activeMenu.value = label
}

function approveQuote() {
  reviewStatus.value = 'approved'
  ElMessage.success('报价已人工确认，模拟推送至企业微信')
}

function requestEdit() {
  reviewStatus.value = 'editing'
  ElMessage.warning('已退回 AI 修改报价')
}

function logout() { auth.logout(); router.push('/login') }
</script>

<template>
  <div class="opc-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark"><el-icon><Grid /></el-icon></div>
        <div><strong>丝网 OPC</strong><span>智能业务工作台</span></div>
      </div>
      <nav class="side-nav">
        <button v-for="item in menuItems" :key="item.label" :class="['nav-item', { active: activeMenu === item.label }]" @click="chooseMenu(item.label)">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><span v-if="item.label === '询盘中心'" class="nav-badge">8</span>
        </button>
      </nav>
      <div class="sidebar-foot">
        <div class="factory-state"><i></i> 5 家合作工厂在线</div>
        <p>人负责客户、技术和品控<br />AI 负责效率，工厂负责交付</p>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div><h1>丝网 OPC 工作台</h1><p>从询盘识别、自动核价到人工确认，全流程可追溯</p></div>
        <div class="top-actions">
          <button class="icon-button"><el-icon><Bell /></el-icon><i></i></button>
          <el-dropdown @command="(cmd: string) => cmd === 'logout' && logout()">
            <button class="user-button"><span class="avatar">徐</span><span>{{ auth.username || '管理员' }}</span><el-icon><ArrowDown /></el-icon></button>
            <template #dropdown><el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </header>

      <div class="page-body">
        <template v-if="activeMenu === '工作台'">
          <section class="metrics-grid">
          <article v-for="metric in metrics" :key="metric.label" class="metric-card">
            <div :class="['metric-icon', metric.tone]"><el-icon><component :is="metric.icon" /></el-icon></div>
            <div class="metric-copy"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div><small>{{ metric.change }}</small>
          </article>
        </section>

        <section class="content-grid">
          <article class="panel review-panel">
            <div class="panel-head">
              <div><span class="eyebrow">AI QUOTE REVIEW</span><h2>报价单审核</h2></div>
              <div :class="['review-state', reviewStatus]"><span></span>{{ statusText }}</div>
            </div>
            <div class="quote-meta"><span>询盘编号 <b>INQ-20250922001</b></span><span>客户 河北安筑工程有限公司</span><span>今天 10:24</span></div>

            <div class="quote-main">
              <div class="drawing-card">
                <div class="mesh-photo"><div class="mesh-grid"></div><span>图纸识别置信度 <b>96%</b></span></div>
                <div class="drawing-note"><el-icon><DocumentChecked /></el-icon><div><strong>building-mesh-01.pdf</strong><span>2 页 · 1.8 MB · 已解析</span></div></div>
                <p>用于建筑工地临边防护，须符合国家安全标准，按图纸尺寸报价。</p>
              </div>

              <div class="spec-card">
                <div class="spec-title"><h3>客户需求信息</h3><button><el-icon><Edit /></el-icon> 编辑规格</button></div>
                <dl>
                  <div><dt>产品类型</dt><dd>建筑防护网</dd></div><div><dt>材质</dt><dd>低碳钢丝</dd></div>
                  <div><dt>丝径</dt><dd>3.5 mm</dd></div><div><dt>网孔</dt><dd>50 × 50 mm</dd></div>
                  <div><dt>数量</dt><dd>2,000 平方米</dd></div><div><dt>表面处理</dt><dd>热镀锌</dd></div>
                  <div><dt>预计交期</dt><dd>15 天</dd></div>
                </dl>
                <div class="price-box">
                  <div><span>AI 建议报价</span><strong>¥ 58,600</strong></div>
                  <div class="price-detail"><span>材料 ¥39,200</span><span>加工 ¥8,400</span><span>包装物流 ¥4,000</span><span>毛利 13.5%</span></div>
                </div>
              </div>
            </div>

            <div class="review-actions">
              <div><el-icon><InfoFilled /></el-icon><span>价格由规则引擎计算，AI 不直接填写价格</span></div>
              <button class="secondary" @click="requestEdit"><el-icon><RefreshLeft /></el-icon>退回修改</button>
              <button class="primary" @click="approveQuote"><el-icon><ChatDotRound /></el-icon>确认并发送企业微信</button>
            </div>
          </article>

          <aside class="right-column">
            <article class="panel process-panel">
              <div class="panel-head compact"><div><span class="eyebrow">WORKFLOW</span><h2>处理流程</h2></div><span class="elapsed">已用时 2m 18s</span></div>
              <ol class="timeline">
                <li class="done"><i><el-icon><Check /></el-icon></i><div><strong>AI 提取规格</strong><span>自动识别图纸和客户需求</span></div><time>10:24</time></li>
                <li class="done"><i><el-icon><Check /></el-icon></i><div><strong>规则引擎核价</strong><span>材料、加工、包装和利润校验</span></div><time>10:26</time></li>
                <li :class="reviewStatus === 'approved' ? 'done' : 'active'"><i><el-icon><User /></el-icon></i><div><strong>人工确认</strong><span>审核技术参数与最终报价</span></div><time>当前</time></li>
                <li :class="reviewStatus === 'approved' ? 'active' : ''"><i><el-icon><OfficeBuilding /></el-icon></i><div><strong>工厂排产</strong><span>推荐工厂并确认交期</span></div></li>
              </ol>
            </article>

            <article class="panel factory-panel">
              <div class="panel-head compact"><div><span class="eyebrow">FACTORY MATCH</span><h2>推荐合作工厂</h2></div><button>查看全部</button></div>
              <div class="factory-row"><div class="factory-logo">安</div><div><strong>安平恒泰丝网厂</strong><span>焊接网 · 热镀锌 · 出口包装</span></div><b>92分</b></div>
              <div class="factory-tags"><span>预计交期 13天</span><span>准时率 96%</span><span>距离 8.4km</span></div>
            </article>
          </aside>
        </section>

          <section class="panel inquiries-panel">
          <div class="panel-head compact"><div><span class="eyebrow">RECENT RFQ</span><h2>最近询盘</h2></div><button>进入询盘中心 <el-icon><ArrowRight /></el-icon></button></div>
          <div class="inquiry-table">
            <div class="table-row table-head"><span>询盘编号</span><span>客户</span><span>产品</span><span>来源</span><span>时间</span><span>状态</span></div>
            <div v-for="item in inquiries" :key="item.id" class="table-row"><b>{{ item.id }}</b><span>{{ item.customer }}</span><span>{{ item.product }}</span><span>{{ item.source }}</span><span>{{ item.time }}</span><em :class="item.status">{{ item.status }}</em></div>
          </div>
          </section>
        </template>
        <OperationsModule v-else :module="activeMenu" />
      </div>
    </main>
  </div>
</template>

<style scoped>
.opc-shell { min-height: 100vh; display: flex; background: #f3f6fa; color: #17243a; text-align: left; }
.sidebar { width: 232px; flex: 0 0 232px; background: linear-gradient(180deg,#102b4b,#0b223d); color: #d5e3f1; display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; }
.brand-block { height: 78px; display: flex; align-items: center; gap: 12px; padding: 0 22px; border-bottom: 1px solid rgba(255,255,255,.08); }.brand-mark { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 10px; background: linear-gradient(135deg,#3b82f6,#14b8a6); color: white; font-size: 22px; }.brand-block strong { display: block; color: white; font-size: 19px; }.brand-block span { display: block; font-size: 11px; opacity: .68; margin-top: 2px; }
.side-nav { padding: 20px 12px; display: grid; gap: 6px; }.nav-item { height: 46px; border: 0; border-radius: 8px; display: flex; align-items: center; gap: 12px; padding: 0 14px; color: #b9cadb; background: transparent; font-size: 14px; cursor: pointer; text-align: left; }.nav-item .el-icon { font-size: 18px; }.nav-item:hover { background: rgba(255,255,255,.06); color: white; }.nav-item.active { background: linear-gradient(90deg,#2676e9,#2d86ed); color: white; box-shadow: 0 7px 18px rgba(35,112,223,.25); }.nav-badge { margin-left: auto; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px; display: grid; place-items: center; background: #ff8b47; color: white; font-size: 11px; }
.sidebar-foot { margin-top: auto; padding: 18px 18px 24px; border-top: 1px solid rgba(255,255,255,.08); }.factory-state { font-size: 12px; color: #bfead9; margin-bottom: 11px; }.factory-state i { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 0 4px rgba(52,211,153,.12); margin-right: 7px; }.sidebar-foot p { font-size: 11px; line-height: 1.8; opacity: .55; }
.workspace { min-width: 0; flex: 1; }.topbar { height: 78px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; background: white; border-bottom: 1px solid #e7edf4; }.topbar h1 { margin: 0; font-size: 22px; line-height: 1.2; font-weight: 700; color: #12213a; }.topbar p { color: #8592a6; font-size: 12px; margin: 5px 0 0; }.top-actions { display: flex; align-items: center; gap: 12px; }.icon-button,.user-button { border: 0; background: transparent; cursor: pointer; }.icon-button { position: relative; width: 38px; height: 38px; border-radius: 10px; font-size: 18px; color: #5f6e82; }.icon-button i { position: absolute; right: 8px; top: 7px; width: 6px; height: 6px; border-radius: 50%; background: #ff654f; }.user-button { display: flex; align-items: center; gap: 8px; color: #33435b; }.avatar { width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center; background: #e3edff; color: #2268d9; font-weight: 700; }
.page-body { padding: 22px 26px 34px; max-width: 1500px; margin: 0 auto; }.metrics-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 16px; margin-bottom: 18px; }.metric-card { height: 102px; background: white; border: 1px solid #e6edf4; border-radius: 12px; display: flex; align-items: center; padding: 19px; box-shadow: 0 4px 14px rgba(25,49,82,.04); }.metric-icon { width: 48px; height: 48px; display: grid; place-items: center; border-radius: 12px; font-size: 22px; margin-right: 14px; }.metric-icon.blue { background: #eaf2ff; color: #2d75e7; }.metric-icon.teal { background: #e5f8f5; color: #11a990; }.metric-icon.orange { background: #fff0e5; color: #f28a39; }.metric-icon.purple { background: #efedff; color: #7067e8; }.metric-copy span { display: block; color: #7e8b9e; font-size: 12px; }.metric-copy strong { display: block; font-size: 27px; margin-top: 4px; color: #14233b; }.metric-card small { margin-left: auto; align-self: flex-start; color: #25a77f; background: #ecfaf5; padding: 3px 7px; border-radius: 10px; font-size: 10px; }
.content-grid { display: grid; grid-template-columns: minmax(0,1.85fr) minmax(310px,.7fr); gap: 18px; align-items: start; }.panel { background: white; border: 1px solid #e3eaf2; border-radius: 12px; box-shadow: 0 5px 18px rgba(23,47,79,.045); }.review-panel { padding: 20px; }.panel-head { display: flex; align-items: center; justify-content: space-between; }.panel-head h2 { margin: 2px 0 0; font-size: 19px; color: #17263d; }.panel-head.compact h2 { font-size: 17px; }.eyebrow { color: #6b8aaf; font-size: 9px; font-weight: 800; letter-spacing: 1.3px; }.review-state { display: flex; align-items: center; gap: 7px; font-size: 11px; padding: 7px 10px; border-radius: 16px; }.review-state span { width: 7px; height: 7px; border-radius: 50%; }.review-state.pending { color: #ca761f; background: #fff4df; }.review-state.pending span { background: #f6a73e; }.review-state.approved { color: #158461; background: #e7f8f2; }.review-state.approved span { background: #18ae7e; }.review-state.editing { color: #c14a4a; background: #fff0f0; }.review-state.editing span { background: #e45e5e; }
.quote-meta { display: flex; gap: 25px; color: #8591a2; font-size: 10px; padding: 13px 0; margin: 13px 0 16px; border-top: 1px solid #edf1f5; border-bottom: 1px solid #edf1f5; }.quote-meta b { color: #3d5e8a; }.quote-main { display: grid; grid-template-columns: 34% 1fr; gap: 16px; }.drawing-card,.spec-card { border: 1px solid #e4eaf1; border-radius: 10px; overflow: hidden; }.mesh-photo { position: relative; height: 176px; padding: 16px; background: linear-gradient(145deg,#3d4e61,#172b40); overflow: hidden; }.mesh-grid { position: absolute; inset: -20px; background-image: linear-gradient(rgba(202,217,228,.65) 2px,transparent 2px),linear-gradient(90deg,rgba(202,217,228,.65) 2px,transparent 2px); background-size: 29px 29px; transform: perspective(500px) rotateX(62deg) rotateZ(-8deg) scale(1.35); }.mesh-photo > span { position: absolute; left: 13px; bottom: 12px; background: rgba(10,28,44,.78); color: #d6e2eb; padding: 6px 8px; font-size: 9px; border-radius: 5px; }.mesh-photo b { color: #52d6af; }.drawing-note { display: flex; gap: 9px; align-items: center; padding: 12px; border-bottom: 1px solid #e9eef4; color: #3976c9; }.drawing-note strong { display: block; color: #34465e; font-size: 11px; }.drawing-note span { display: block; color: #98a3b1; font-size: 9px; margin-top: 2px; }.drawing-card > p { color: #6f7d90; font-size: 10px; line-height: 1.6; padding: 12px; }
.spec-card { padding: 15px; }.spec-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 9px; }.spec-title h3 { font-size: 13px; margin: 0; }.spec-title button,.panel-head button { border: 0; background: transparent; color: #3277d6; font-size: 10px; cursor: pointer; display: flex; align-items: center; gap: 4px; }.spec-card dl { border: 1px solid #e5ebf1; border-radius: 7px; overflow: hidden; margin: 0; }.spec-card dl div { display: grid; grid-template-columns: 38% 1fr; min-height: 31px; border-bottom: 1px solid #e9eef3; }.spec-card dl div:last-child { border-bottom: 0; }.spec-card dt,.spec-card dd { margin: 0; padding: 7px 10px; font-size: 10px; }.spec-card dt { color: #78879a; background: #f7f9fc; border-right: 1px solid #e9eef3; }.spec-card dd { color: #30445e; font-weight: 600; }.price-box { margin-top: 12px; background: linear-gradient(90deg,#ecf8f5,#f3fbf9); border: 1px solid #d8f0e9; border-radius: 8px; padding: 12px; }.price-box > div:first-child { display: flex; align-items: center; justify-content: space-between; }.price-box span { color: #66788b; font-size: 10px; }.price-box strong { color: #0d8d70; font-size: 21px; }.price-detail { display: flex; flex-wrap: wrap; gap: 5px 13px; border-top: 1px solid #d8ece7; margin-top: 8px; padding-top: 8px; }.price-detail span { font-size: 8px; }
.review-actions { display: flex; align-items: center; gap: 9px; border-top: 1px solid #edf1f5; margin-top: 17px; padding-top: 15px; }.review-actions > div { display: flex; align-items: center; gap: 5px; margin-right: auto; color: #8995a5; font-size: 9px; }.review-actions button { height: 36px; padding: 0 14px; border-radius: 7px; display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 11px; font-weight: 600; }.secondary { border: 1px solid #cfdae6; background: white; color: #54677e; }.primary { border: 1px solid #08a37f; background: linear-gradient(90deg,#0db18b,#079878); color: white; box-shadow: 0 5px 12px rgba(8,161,126,.18); }
.right-column { display: grid; gap: 18px; }.process-panel,.factory-panel { padding: 18px; }.elapsed { color: #8795a6; font-size: 9px; }.timeline { list-style: none; margin: 18px 0 0; padding: 0; }.timeline li { position: relative; display: grid; grid-template-columns: 27px 1fr auto; gap: 10px; min-height: 61px; }.timeline li:not(:last-child)::after { content: ''; position: absolute; left: 13px; top: 26px; width: 1px; height: 34px; background: #dce5ef; }.timeline i { width: 27px; height: 27px; border-radius: 50%; display: grid; place-items: center; background: #eef2f7; color: #a6b0bd; font-style: normal; font-size: 12px; z-index: 1; }.timeline li.done i { background: #1ab28b; color: white; }.timeline li.active i { background: #2f79e5; color: white; box-shadow: 0 0 0 5px #e6f0ff; }.timeline strong { display: block; color: #33465e; font-size: 11px; }.timeline span { display: block; color: #929dac; font-size: 8px; margin-top: 4px; line-height: 1.4; }.timeline time { color: #9aa5b4; font-size: 8px; }.factory-row { display: grid; grid-template-columns: 38px 1fr auto; gap: 9px; align-items: center; margin-top: 16px; }.factory-logo { width: 38px; height: 38px; border-radius: 9px; display: grid; place-items: center; background: #e9f1ff; color: #2b6cca; font-weight: 800; }.factory-row strong { display: block; font-size: 11px; }.factory-row span { display: block; color: #929dac; font-size: 8px; margin-top: 3px; }.factory-row b { color: #16a47f; font-size: 12px; }.factory-tags { display: flex; gap: 5px; margin-top: 13px; }.factory-tags span { color: #59718e; font-size: 8px; background: #f1f5f9; padding: 5px 6px; border-radius: 4px; }
.inquiries-panel { margin-top: 18px; padding: 18px 20px 10px; }.inquiry-table { margin-top: 13px; }.table-row { display: grid; grid-template-columns: 1.25fr 1.2fr 1fr .75fr .6fr .65fr; gap: 12px; align-items: center; min-height: 42px; border-top: 1px solid #eef2f6; font-size: 10px; color: #53657b; }.table-row b { color: #305b8f; }.table-head { min-height: 31px; border: 0; color: #97a2af; font-size: 9px; }.table-row em { width: fit-content; font-style: normal; border-radius: 10px; padding: 4px 8px; font-size: 8px; }.table-row em.待确认 { color: #c6771f; background: #fff2df; }.table-row em.识别中 { color: #296fd0; background: #e9f2ff; }.table-row em.已报价 { color: #148566; background: #e7f8f1; }
@media (max-width: 1100px) { .sidebar { width: 190px; flex-basis: 190px; }.metrics-grid { grid-template-columns: repeat(2,1fr); }.content-grid { grid-template-columns: 1fr; }.right-column { grid-template-columns: 1fr 1fr; } }
@media (max-width: 760px) { .sidebar { display: none; }.page-body { padding: 15px; }.metrics-grid,.quote-main,.right-column { grid-template-columns: 1fr; }.topbar { padding: 0 16px; }.topbar p { display: none; }.review-actions { flex-wrap: wrap; }.review-actions > div { width: 100%; }.table-row { grid-template-columns: 1.5fr 1fr .7fr; }.table-row > :nth-child(2),.table-row > :nth-child(5),.table-row > :nth-child(6) { display: none; } }
</style>
