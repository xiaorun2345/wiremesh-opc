import axios from 'axios'
import { ElMessage } from 'element-plus'

// `npm run dev:mock` 使用模拟数据；普通 `npm run dev` 连接真实后端。
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const TOKEN    = 'mock-token-openspec-2026'

// let 而非 const，支持上传后动态添加新任务
let MOCK_TASKS: Record<string, unknown>[] = [
  {
    task_id: 'task-001', status: 'SUCCESS', current_step: null, progress: 100,
    file_name: '建筑防护网图纸.dxf', file_type: 'dxf',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
    intermediate_data: null, error_msg: null,
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 120 },
      { agent: 'CadParseAgent',     status: 'SUCCESS', duration_ms: 4200 },
      { agent: 'QuantityCalcAgent', status: 'SUCCESS', duration_ms: 380 },
      { agent: 'BudgetCheckAgent',  status: 'SUCCESS', duration_ms: 2100 },
      { agent: 'ReportExportAgent', status: 'SUCCESS', duration_ms: 650 },
    ],
  },
  {
    task_id: 'task-002', status: 'RUNNING', current_step: 'BudgetCheckAgent', progress: 60,
    file_name: '卧室施工图.pdf', file_type: 'pdf',
    created_at: new Date(Date.now() - 600000).toISOString(),
    updated_at: new Date().toISOString(),
    intermediate_data: null, error_msg: null,
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 95 },
      { agent: 'TextExtractAgent',  status: 'SUCCESS', duration_ms: 8500 },
      { agent: 'QuantityCalcAgent', status: 'SUCCESS', duration_ms: 420 },
      { agent: 'BudgetCheckAgent',  status: 'RUNNING', duration_ms: null },
      { agent: 'ReportExportAgent', status: 'PENDING', duration_ms: null },
    ],
  },
  {
    task_id: 'task-003', status: 'FAILED', current_step: 'CadParseAgent', progress: 20,
    file_name: '全屋户型图.dwg', file_type: 'dwg',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 7000000).toISOString(),
    intermediate_data: null,
    error_msg: 'ezdxf 读取失败：文件格式不支持（天正专有格式）',
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 88 },
      { agent: 'CadParseAgent',     status: 'FAILED',  duration_ms: 1200 },
      { agent: 'QuantityCalcAgent', status: 'PENDING', duration_ms: null },
      { agent: 'BudgetCheckAgent',  status: 'PENDING', duration_ms: null },
      { agent: 'ReportExportAgent', status: 'PENDING', duration_ms: null },
    ],
  },
  {
    task_id: 'task-004', status: 'PAUSED', current_step: 'QuantityCalcAgent', progress: 40,
    file_name: '厨房改造方案.png', file_type: 'png',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    updated_at: new Date(Date.now() - 900000).toISOString(),
    intermediate_data: {
      paused_at_step: 'QuantityCalcAgent',
      review_hint: '视觉解析结果置信度较低，请确认丝径、网孔和尺寸后续跑',
      rooms: [{ name: '厨房', area_m2: 8.5 }, { name: '餐厅', area_m2: 12.0 }],
    },
    error_msg: null,
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 110 },
      { agent: 'VisionParseAgent',  status: 'SUCCESS', duration_ms: 6800 },
      { agent: 'QuantityCalcAgent', status: 'PAUSED',  duration_ms: null },
      { agent: 'BudgetCheckAgent',  status: 'PENDING', duration_ms: null },
      { agent: 'ReportExportAgent', status: 'PENDING', duration_ms: null },
    ],
  },
]

function mockResponse(url: string, method: string, data?: unknown): unknown {
  // 认证
  if (url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh'))
    return { access_token: TOKEN, refresh_token: TOKEN, token_type: 'bearer' }
  if (url.includes('/auth/preferences') && method === 'GET')
    return { default_floor_height: 2800, preferred_material: '涂料', waterproof_standard: 'GB50327', extra: {} }
  if (url.includes('/auth/preferences') && method === 'PUT')
    return data

  // 丝网确定性报价（与后端 wire-mesh-v1 公式保持一致）
  if (url.includes('/quotes/preview') && method === 'POST') {
    const spec = data as Record<string, number | string>
    const materialPrice: Record<string, number> = {
      low_carbon_steel: 4.6, galvanized_steel: 5.4,
      stainless_304: 15.8, stainless_316: 23.5,
    }
    const processPrice: Record<string, number> = {
      welded_mesh: 4.2, fence_mesh: 5.8, hexagonal_mesh: 3.6,
      screen_mesh: 7.5, expanded_mesh: 6.8,
    }
    const surfacePrice: Record<string, number> = {
      none: 0, electro_galvanized: 0.65, hot_dip_galvanized: 1.15,
      pvc_coated: 1.45, powder_coated: 1.75,
    }
    const packagePrice: Record<string, number> = { bulk: 0.25, pallet: 0.75, export: 1.2 }
    const factor: Record<string, number> = { welded_mesh: 1, fence_mesh: 1.08, hexagonal_mesh: 0.82, screen_mesh: 1.12, expanded_mesh: 1.18 }
    const area = Number(spec.width_m) * Number(spec.length_m) * Number(spec.quantity)
    const kgPerM = Number(spec.wire_diameter_mm) ** 2 / 162.2
    const kgPerM2 = kgPerM * (2 / (Number(spec.mesh_size_mm) / 1000)) * factor[String(spec.product_type)]
    const weight = kgPerM2 * area
    const material = weight * materialPrice[String(spec.material)]
    const processing = area * processPrice[String(spec.product_type)]
    const surface = weight * surfacePrice[String(spec.surface_treatment)]
    const packaging = area * packagePrice[String(spec.packaging)]
    const cost = material + processing + surface + packaging + Number(spec.freight || 0)
    const total = cost / (1 - Number(spec.margin_rate))
    return {
      quote_id: `QT-MOCK-${Date.now()}`,
      status: 'DRAFT', spec, area_m2: Number(area.toFixed(3)),
      total_weight_kg: Number(weight.toFixed(2)),
      costs: {
        material: Number(material.toFixed(2)), processing: Number(processing.toFixed(2)),
        surface: Number(surface.toFixed(2)), packaging: Number(packaging.toFixed(2)),
        freight: Number(spec.freight || 0), total: Number(cost.toFixed(2)),
      },
      margin_rate: Number(spec.margin_rate), quote_total: Number(total.toFixed(2)),
      unit_price_m2: Number((total / area).toFixed(2)), currency: spec.currency,
      formula_version: 'wire-mesh-v1',
      factory_matches: [{ id: 'factory-hengtai', name: '安平恒泰丝网厂', score: 92, lead_days: 13 }],
      warnings: [],
    }
  }

  // 任务列表（精确匹配 /tasks 或 /tasks?...）
  if (/\/tasks(\?.*)?$/.test(url) && method === 'GET') {
    const params = new URLSearchParams(url.includes('?') ? url.split('?')[1] : '')
    const status = params.get('status')
    const limit  = parseInt(params.get('limit')  || '20')
    const offset = parseInt(params.get('offset') || '0')
    let tasks = [...MOCK_TASKS]
    if (status) tasks = tasks.filter(t => t.status === status)
    return tasks.slice(offset, offset + limit)
  }

  // 上传：创建新任务并插入 MOCK_TASKS，刷新列表时能看到
  if (url.includes('/tasks/upload')) {
    const fd = data as FormData
    const file = fd?.get?.('file')
    const fileName = file instanceof File ? file.name : 'uploaded.pdf'
    const ext = fileName.split('.').pop()?.toLowerCase() || 'pdf'
    const now = new Date().toISOString()
    const newTask: Record<string, unknown> = {
      task_id: `task-${Date.now()}`,
      status: 'PENDING',
      current_step: null,
      progress: 0,
      file_name: fileName,
      file_type: ext,
      created_at: now,
      updated_at: now,
      intermediate_data: null,
      error_msg: null,
      steps: [],
    }
    // 插入到列表最前面，刷新时能看到
    MOCK_TASKS = [newTask, ...MOCK_TASKS]
    return newTask
  }

  // 续跑
  const resumeM = url.match(/\/tasks\/([^/?]+)\/resume/)
  if (resumeM)
    return { task_id: resumeM[1], status: 'RUNNING', resumed_from_step: 'QuantityCalcAgent' }

  // 报告元数据
  const reportM = url.match(/\/reports\/([^/?]+)$/)
  if (reportM && method === 'GET')
    return { task_id: reportM[1], pdf_available: true, excel_available: true, created_at: new Date().toISOString() }

  // 报告下载
  if (url.includes('/download'))
    return { message: 'Mock 模式下报告下载不可用，请连接真实后端' }

  // 任务详情 / 取消
  const taskM = url.match(/\/tasks\/([^/?]+)$/)
  if (taskM && method === 'GET') {
    const task = MOCK_TASKS.find(t => t.task_id === taskM[1])
    return task ?? { detail: { error: 'TASK_NOT_FOUND', message: '任务不存在' } }
  }
  if (taskM && method === 'DELETE') return {}

  return { message: 'mock ok' }
}

// ── Axios 实例 ────────────────────────────────────────────────
const client = axios.create({
  baseURL: '/api/v2',
  timeout: 30000,
})

// 请求拦截器：Mock 模式直接返回假数据，不发真实请求
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  if (USE_MOCK) {
    // 取消真实请求，通过 adapter 返回 mock 数据
    config.adapter = async (cfg) => {
      const url    = (cfg.url || '').replace(/^\/api\/v2/, '')
      const method = (cfg.method || 'get').toUpperCase()
      // FormData（文件上传）不能 JSON.parse，直接传 undefined
      const body = cfg.data instanceof FormData
        ? cfg.data  // 直接传 FormData，让 mockResponse 自己处理
        : (cfg.data && typeof cfg.data === 'string' ? JSON.parse(cfg.data) : cfg.data)
      // axios 的 params 单独传，需要合并到 url 里供 mock 使用
      const params = cfg.params ? new URLSearchParams(cfg.params).toString() : ''
      const fullUrl = params ? `${url}?${params}` : url
      const result = mockResponse(fullUrl, method, body)
      return {
        data:       result,
        status:     200,
        statusText: 'OK',
        headers:    {},
        config:     cfg,
      }
    }
  }

  return config
})

// 响应拦截器：401 自动刷新 Token（Mock 模式下不会触发）
let isRefreshing = false
let pendingQueue: Array<(token: string) => void> = []

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true

      if (isRefreshing) {
        return new Promise((resolve) => {
          pendingQueue.push((token) => {
            original.headers.Authorization = `Bearer ${token}`
            resolve(client(original))
          })
        })
      }

      isRefreshing = true
      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) throw new Error('no refresh token')

        const { data } = await axios.post('/api/v2/auth/refresh', {
          refresh_token: refreshToken,
        })
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)

        pendingQueue.forEach((cb) => cb(data.access_token))
        pendingQueue = []

        original.headers.Authorization = `Bearer ${data.access_token}`
        return client(original)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      } finally {
        isRefreshing = false
      }
    }

    // 友好错误提示，不暴露技术细节
    const status = error.response?.status
    const serverMsg = error.response?.data?.detail?.message
      || error.response?.data?.message

    let msg = '服务暂时不可用，请稍后重试'
    if (serverMsg) {
      msg = serverMsg
    } else if (status === 401) {
      msg = '登录已过期，请重新登录'
    } else if (status === 403) {
      msg = '无权限执行此操作'
    } else if (status === 404) {
      msg = '请求的资源不存在'
    } else if (status === 400) {
      msg = '请求参数有误，请检查后重试'
    } else if (status === 409) {
      msg = '操作冲突，请刷新后重试'
    } else if (status === 500) {
      msg = '服务器内部错误，请联系管理员'
    } else if (!error.response) {
      msg = '网络连接失败，请检查网络后重试'
    }

    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default client
