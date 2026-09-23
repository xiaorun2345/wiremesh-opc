import client from './client'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE = '/api/v1'

export interface StandardInfo {
  filename: string
  standard_name: string
  page_count: number
  section_count: number
  categories: string[]
  status: string
  created_at: string
}

export interface QueryResult {
  standard_name: string
  section: string
  chapter: string
  content: string
  keywords: string[]
  is_mandatory: boolean
  score: number
}

/** 上传 PDF 标准文档 */
export async function uploadStandard(file: File) {
  const auth = useAuthStore()
  const formData = new FormData()
  formData.append('file', file)

  const resp = await axios.post(`${API_BASE}/standards/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
      'Authorization': `Bearer ${auth.accessToken}`,
    },
  })
  return resp.data
}

/** 查询已导入的标准列表 */
export async function listStandards() {
  const resp = await client.get(`${API_BASE}/standards/list`)
  return resp.data as { total: number; standards: StandardInfo[] }
}

/** RAG 检索条文 */
export async function queryStandards(query: string, topK = 5) {
  const resp = await client.post(`${API_BASE}/standards/query`, {
    query,
    top_k: topK,
  })
  return resp.data as { query: string; results: QueryResult[] }
}

/** 删除标准文档 */
export async function deleteStandard(filename: string) {
  const resp = await client.delete(`${API_BASE}/standards/${filename}`)
  return resp.data
}

/** 查询导入状态 */
export async function getImportStatus(filename: string) {
  const resp = await client.get(`${API_BASE}/standards/status/${filename}`)
  return resp.data
}
