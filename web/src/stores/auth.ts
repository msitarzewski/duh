import { create } from 'zustand'
import { api } from '@/api/client'
import type { UserInfo } from '@/api/types'

export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'error'

const TOKEN_KEY = 'duh_token'

interface AuthState {
  token: string | null
  user: UserInfo | null
  status: AuthStatus
  error: string | null
  authRequired: boolean | null

  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  status: 'idle',
  error: null,
  authRequired: null,

  login: async (email, password) => {
    set({ status: 'loading', error: null })
    try {
      const res = await api.login({ email, password })
      localStorage.setItem(TOKEN_KEY, res.access_token)
      const user = await api.me()
      set({
        token: res.access_token,
        user,
        status: 'authenticated',
        error: null,
      })
    } catch (e) {
      set({ status: 'error', error: (e as Error).message })
    }
  },

  register: async (email, password, displayName) => {
    set({ status: 'loading', error: null })
    try {
      const res = await api.register({
        email,
        password,
        display_name: displayName,
      })
      localStorage.setItem(TOKEN_KEY, res.access_token)
      const user = await api.me()
      set({
        token: res.access_token,
        user,
        status: 'authenticated',
        error: null,
      })
    } catch (e) {
      set({ status: 'error', error: (e as Error).message })
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    set({
      token: null,
      user: null,
      status: 'idle',
      error: null,
    })
  },

  initialize: async () => {
    // Check if auth is required
    try {
      const { auth_required } = await api.authStatus()
      set({ authRequired: auth_required })

      if (!auth_required) {
        // Dev mode: allow guest access
        set({
          status: 'authenticated',
          user: {
            id: 'guest',
            email: '',
            display_name: 'Guest',
            role: 'admin',
            is_active: true,
          },
        })
        return
      }
    } catch {
      // If auth status endpoint doesn't exist, assume auth not required
      set({
        authRequired: false,
        status: 'authenticated',
        user: {
          id: 'guest',
          email: '',
          display_name: 'Guest',
          role: 'admin',
          is_active: true,
        },
      })
      return
    }

    // Auth is required — check for existing token
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      set({ status: 'idle' })
      return
    }

    set({ token, status: 'loading' })
    try {
      const user = await api.me()
      set({ user, status: 'authenticated' })
    } catch {
      // Token invalid or expired
      localStorage.removeItem(TOKEN_KEY)
      set({ token: null, status: 'idle' })
    }
  },
}))
