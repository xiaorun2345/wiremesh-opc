// Mock 数据：模拟所有后端 API 接口
// 前端独立运行时使用，不需要启动后端

const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtb2NrLXVzZXItMDAxIiwiZXhwIjo5OTk5OTk5OTk5fQ.mock'

// 模拟任务数据
const mockTasks = [
  {
    task_id: 'task-001',
    status: 'SUCCESS',
    current_step: null,
    progress: 100,
    file_name: '客厅装修平面图.dxf',
    file_type: 'dxf',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
    intermediate_data: null,
    error_msg: null,
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 120 },
      { agent: 'CadParseAgent',     status: 'SUCCESS', duration_ms: 4200 },
      { agent: 'QuantityCalcAgent', status: 'SUCCESS', duration_ms: 380 },
      { agent: 'BudgetCheckAgent',  status: 'SUCCESS', duration_ms: 2100 },
      { agent: 'ReportExportAgent', status: 'SUCCESS', duration_ms: 650 },
    ],
  },
  {
    task_id: 'task-002',
    status: 'RUNNING',
    current_step: 'BudgetCheckAgent',
    progress: 60,
    file_name: '卧室施工图.pdf',
    file_type: 'pdf',
    created_at: new Date(Date.now() - 600000).toISOString(),
    updated_at: new Date().toISOString(),
    intermediate_data: null,
    error_msg: null,
    steps: [
      { agent: 'FileClassifyAgent', status: 'SUCCESS', duration_ms: 95 },
      { agent: 'TextExtractAgent',  status: 'SUCCESS', duration_ms: 8500 },
      { agent: 'QuantityCalcAgent', status: 'SUCCESS', duration_ms: 420 },
      { agent: 'BudgetCheckAgent',  status: 'RUNNING', duration_ms: null },
      { agent: 'ReportExportAgent', status: 'PENDING', duration_ms: null },
    ],
  },
  {
    task_id: 'task-003',
    status: 'FAILED',
    current_step: 'CadParseAgent',
    progress: 20,
    file_name: '全屋户型图.dwg',
    file_type: 'dwg',
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
    task_id: 'task-004',
    status: 'PAUSED',
    current_step: 'QuantityCalcAgent',
    progress: 40,
    file_name: '厨房改造方案.png',
    file_type: 'png',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    updated_at: new Date(Date.now() - 900000).toISOString(),
    intermediate_data: {
      paused_at_step: 'QuantityCalcAgent',
      review_hint: '视觉解析结果置信度较低，请确认房间面积后续跑',
      rooms: [{ name: '厨房', area_m2: 8.5 }, { name: '餐厅', area_m2: 12.0 }],
      walls: [{ total_length: 18000, segment_count: 6 }],
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

export default [
  // ── 健康检查 ──────────────────────────────────────────────
  {
    url: '/health',
    method: 'get',
    response: () => ({ status: 'ok', app: 'OpenSpec', env: 'mock' }),
  },

  // ── 认证接口 ──────────────────────────────────────────────
  {
    url: '/api/v2/auth/login',
    method: 'post',
    response: ({ body }: any) => {
      if (body.password === 'wrong') {
        return { code: 401, message: '用户名或密码错误' }
      }
      return { access_token: token, refresh_token: token, token_type: 'bearer' }
    },
  },
  {
    url: '/api/v2/auth/register',
    method: 'post',
    response: () => ({ access_token: token, refresh_token: token, token_type: 'bearer' }),
  },
  {
    url: '/api/v2/auth/refresh',
    method: 'post',
    response: () => ({ access_token: token, refresh_token: token, token_type: 'bearer' }),
  },
  {
    url: '/api/v2/auth/preferences',
    method: 'get',
    response: () => ({
      default_floor_height: 2800,
      preferred_material: '涂料',
      waterproof_standard: 'GB50327',
      extra: {},
    }),
  },
  {
    url: '/api/v2/auth/preferences',
    method: 'put',
    response: ({ body }: any) => body,
  },

  // ── 任务列表 ──────────────────────────────────────────────
  {
    url: '/api/v2/tasks',
    method: 'get',
    response: ({ query }: any) => {
      let tasks = [...mockTasks]
      if (query.status) {
        tasks = tasks.filter(t => t.status === query.status)
      }
      const limit  = parseInt(query.limit  || '20')
      const offset = parseInt(query.offset || '0')
      return tasks.slice(offset, offset + limit)
    },
  },

  // ── 上传任务 ──────────────────────────────────────────────
  {
    url: '/api/v2/tasks/upload',
    method: 'post',
    response: () => {
      const newTask = {
        task_id: `task-${Date.now()}`,
        status: 'PENDING',
        current_step: null,
        progress: 0,
        file_name: 'uploaded_file.pdf',
        file_type: 'pdf',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        intermediate_data: null,
        error_msg: null,
        steps: [],
      }
      mockTasks.unshift(newTask as any)
      return newTask
    },
  },

  // ── 任务详情 ──────────────────────────────────────────────
  {
    url: '/api/v2/tasks/:id',
    method: 'get',
    response: ({ params }: any) => {
      const task = mockTasks.find(t => t.task_id === params.id)
      if (!task) return { code: 404, detail: { error: 'TASK_NOT_FOUND', message: '任务不存在' } }
      return task
    },
  },
  {
    url: '/api/v2/tasks/:id/resume',
    method: 'post',
    response: ({ params }: any) => ({
      task_id: params.id,
      status: 'RUNNING',
      resumed_from_step: 'QuantityCalcAgent',
    }),
  },
  {
    url: '/api/v2/tasks/:id',
    method: 'delete',
    response: () => ({}),
  },

  // ── 报告接口 ──────────────────────────────────────────────
  {
    url: '/api/v2/reports/:id',
    method: 'get',
    response: ({ params }: any) => {
      const task = mockTasks.find(t => t.task_id === params.id)
      if (!task || task.status !== 'SUCCESS') {
        return { code: 404, detail: { error: 'REPORT_NOT_FOUND', message: '报告不存在' } }
      }
      return {
        task_id: params.id,
        pdf_available: true,
        excel_available: true,
        created_at: new Date().toISOString(),
      }
    },
  },
  {
    url: '/api/v2/reports/:id/download',
    method: 'get',
    rawResponse: async (_req: any, res: any) => {
      res.setHeader('Content-Type', 'application/pdf')
      res.setHeader('Content-Disposition', 'attachment; filename="mock_report.pdf"')
      res.statusCode = 200
      res.end(Buffer.from('%PDF-1.4 Mock Report'))
    },
  },
]
