import client from './client'
import type { ReportMeta } from '@/types'

export const reportsApi = {
  getMeta: (taskId: string) =>
    client.get<ReportMeta>(`/reports/${taskId}`),

  download: async (taskId: string, format: 'pdf' | 'excel' = 'pdf') => {
    const res = await client.get(`/reports/${taskId}/download`, {
      params: { format },
      responseType: 'blob',
    })
    const ext = format === 'pdf' ? 'pdf' : 'xlsx'
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `report_${taskId}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  },
}
