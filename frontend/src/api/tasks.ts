import client from './client'
import type { TaskResponse, ResumeRequest, ResumeResponse } from '@/types'

export const tasksApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return client.post<TaskResponse>('/tasks/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getTask: (taskId: string) =>
    client.get<TaskResponse>(`/tasks/${taskId}`),

  listTasks: (params?: { status?: string; limit?: number; offset?: number }) =>
    client.get<TaskResponse[]>('/tasks', { params }),

  resumeTask: (taskId: string, body: ResumeRequest) =>
    client.post<ResumeResponse>(`/tasks/${taskId}/resume`, body),

  cancelTask: (taskId: string) =>
    client.delete(`/tasks/${taskId}`),
}
