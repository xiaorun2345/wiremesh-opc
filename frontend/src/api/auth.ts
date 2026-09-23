import client from './client'
import type { TokenResponse, UserPreferences } from '@/types'

export const authApi = {
  login: (username: string, password: string) =>
    client.post<TokenResponse>('/auth/login', { username, password }),

  register: (username: string, password: string) =>
    client.post<TokenResponse>('/auth/register', { username, password }),

  refresh: (refresh_token: string) =>
    client.post<TokenResponse>('/auth/refresh', { refresh_token }),

  getPreferences: () =>
    client.get<UserPreferences>('/auth/preferences'),

  updatePreferences: (prefs: UserPreferences) =>
    client.put<UserPreferences>('/auth/preferences', prefs),
}
