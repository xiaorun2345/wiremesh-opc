import client from './client'

export interface QuotePreviewRequest {
  product_type: string
  material: string
  wire_diameter_mm: number
  mesh_size_mm: number
  width_m: number
  length_m: number
  quantity: number
  surface_treatment: string
  packaging: string
  margin_rate: number
  freight: number
  currency: string
}

export const quoteApi = {
  preview(data: QuotePreviewRequest) {
    return client.post('/quotes/preview', data)
  },
  submit(quoteId: string) {
    return client.post(`/quotes/${quoteId}/submit`)
  },
  decide(quoteId: string, decision: 'approve' | 'reject', note = '') {
    return client.post(`/quotes/${quoteId}/decision`, { decision, note })
  },
  download(quoteId: string, format: 'pdf' | 'excel') {
    return client.get(`/quotes/${quoteId}/download`, { params: { format }, responseType: 'blob' })
  },
  convertOrder(quoteId: string, data: Record<string, unknown> = {}) {
    return client.post(`/quotes/${quoteId}/convert-order`, data)
  },
}
