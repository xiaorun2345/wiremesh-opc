import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserPreferences } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const accessToken  = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const username     = ref(localStorage.getItem('username') || '')
  const preferences  = ref<UserPreferences | null>(null)

  const isLoggedIn = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string) {
    accessToken.value  = access
    refreshToken.value = refresh
    localStorage.setItem('access_token',  access)
    localStorage.setItem('refresh_token', refresh)
  }

  async function login(user: string, password: string) {
    const { data } = await authApi.login(user, password)
    setTokens(data.access_token, data.refresh_token)
    username.value = user
    localStorage.setItem('username', user)
  }

  async function register(user: string, password: string) {
    const { data } = await authApi.register(user, password)
    setTokens(data.access_token, data.refresh_token)
    username.value = user
    localStorage.setItem('username', user)
  }

  function logout() {
    accessToken.value  = ''
    refreshToken.value = ''
    username.value     = ''
    preferences.value  = null
    localStorage.clear()
  }

  async function loadPreferences() {
    const { data } = await authApi.getPreferences()
    preferences.value = data
  }

  async function savePreferences(prefs: UserPreferences) {
    const { data } = await authApi.updatePreferences(prefs)
    preferences.value = data
  }

  return {
    accessToken, refreshToken, username, preferences,
    isLoggedIn,
    login, register, logout, loadPreferences, savePreferences,
  }
})
