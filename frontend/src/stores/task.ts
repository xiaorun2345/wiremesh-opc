import { defineStore } from 'pinia'
import { ref } from 'vue'
import { tasksApi } from '@/api/tasks'
import type { TaskResponse } from '@/types'

export const useTaskStore = defineStore('task', () => {
  const tasks       = ref<TaskResponse[]>([])
  const currentTask = ref<TaskResponse | null>(null)
  const loading     = ref(false)
  const total       = ref(0)

  async function fetchTasks(params?: { status?: string; limit?: number; offset?: number }) {
    loading.value = true
    try {
      const { data } = await tasksApi.listTasks(params)
      tasks.value = data
      total.value = data.length
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(taskId: string) {
    const { data } = await tasksApi.getTask(taskId)
    currentTask.value = data
    // 同步更新列表中的对应任务
    const idx = tasks.value.findIndex(t => t.task_id === taskId)
    if (idx !== -1) tasks.value[idx] = data
    return data
  }

  async function uploadFile(file: File): Promise<string> {
    const { data } = await tasksApi.upload(file)
    tasks.value.unshift(data)
    return data.task_id
  }

  async function resumeTask(taskId: string, overrideData: Record<string, unknown> = {}) {
    const { data } = await tasksApi.resumeTask(taskId, { override_data: overrideData })
    await fetchTask(taskId)
    return data
  }

  async function cancelTask(taskId: string) {
    await tasksApi.cancelTask(taskId)
    await fetchTask(taskId)
  }

  return {
    tasks, currentTask, loading, total,
    fetchTasks, fetchTask, uploadFile, resumeTask, cancelTask,
  }
})
