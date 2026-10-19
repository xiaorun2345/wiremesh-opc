// 所有 TypeScript 类型定义，与后端 schemas 对齐

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserPreferences {
  default_floor_height: number
  preferred_material: string
  waterproof_standard: string
  extra: Record<string, unknown>
}

export type TaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'PAUSED'
  | 'CANCELLED'

export type FileType = 'pdf' | 'dwg' | 'dxf' | 'jpg' | 'jpeg' | 'png'

export interface StepStatus {
  agent: string
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED'
  duration_ms: number | null
  attempts?: number
  fallback?: string
  message?: string
}

export interface TaskResponse {
  task_id: string
  status: TaskStatus
  current_step: string | null
  progress: number
  steps: StepStatus[]
  file_name: string
  file_type: FileType
  file_size: number
  created_at: string
  updated_at: string
  intermediate_data: Record<string, unknown> | null
  error_msg: string | null
}

export interface ResumeRequest {
  override_data: Record<string, unknown>
}

export interface ResumeResponse {
  task_id: string
  status: string
  resumed_from_step: string
}

export interface ReportMeta {
  task_id: string
  pdf_available: boolean
  excel_available: boolean
  created_at: string
}

export interface ParseParams {
  engine_mode: 'standard' | 'recovery' | 'dual'
  precision: 'fast' | 'normal' | 'high'
  enable_topology: boolean
  enable_vision_assist: boolean
  floor_height_hint: number
}

// Agent 名称到中文的映射
export const AGENT_LABELS: Record<string, string> = {
  FileClassifyAgent: '📄 文件识别',
  TextExtractAgent:  '📝 PDF 文本提取',
  CadParseAgent:     '📐 CAD 图纸解析',
  VisionParseAgent:  '👁️ 视觉识别',
  QuantityCalcAgent: '📊 工程量计算',
  BudgetCheckAgent:  '✅ 合规审核',
  ReportExportAgent: '📋 报告生成',
  DecisionAgent:     '🧠 智能决策',
  WireMeshSpecAgent: '🧵 丝网规格提取',
  WireMeshQuote:     '💰 规则报价',
  WireMeshReport:    '📄 报价文件生成',
  ParseAgent:        '🔍 图纸解析',
}

// 任务状态对应的 Element Plus 类型
export const STATUS_TYPE: Record<TaskStatus, string> = {
  PENDING:   'info',
  RUNNING:   'primary',
  SUCCESS:   'success',
  FAILED:    'danger',
  PAUSED:    'warning',
  CANCELLED: 'info',
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  PENDING:   '等待中',
  RUNNING:   '处理中',
  SUCCESS:   '已完成',
  FAILED:    '失败',
  PAUSED:    '待审核',
  CANCELLED: '已取消',
}
