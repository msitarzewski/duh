import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mock the API client ──
vi.mock('@/api/client', () => ({
  api: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    authStatus: vi.fn(),
  },
}))

import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'

const mockedApi = vi.mocked(api)

describe('useAuthStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      token: null,
      user: null,
      status: 'idle',
      error: null,
      authRequired: null,
    })
  })

  it('has correct initial state', () => {
    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
    expect(state.status).toBe('idle')
    expect(state.error).toBeNull()
    expect(state.authRequired).toBeNull()
  })

  describe('login', () => {
    it('sets token and user on successful login', async () => {
      mockedApi.login.mockResolvedValue({
        access_token: 'test-token',
        token_type: 'bearer',
        user_id: 'u1',
        role: 'user',
      })
      mockedApi.me.mockResolvedValue({
        id: 'u1',
        email: 'test@test.com',
        display_name: 'Test User',
        role: 'user',
        is_active: true,
      })

      await useAuthStore.getState().login('test@test.com', 'pass123')

      const state = useAuthStore.getState()
      expect(state.status).toBe('authenticated')
      expect(state.token).toBe('test-token')
      expect(state.user?.email).toBe('test@test.com')
      expect(state.error).toBeNull()
      expect(localStorage.getItem('duh_token')).toBe('test-token')
    })

    it('sets error on failed login', async () => {
      mockedApi.login.mockRejectedValue(new Error('Invalid credentials'))

      await useAuthStore.getState().login('bad@test.com', 'wrong')

      const state = useAuthStore.getState()
      expect(state.status).toBe('error')
      expect(state.error).toBe('Invalid credentials')
      expect(state.token).toBeNull()
    })
  })

  describe('register', () => {
    it('sets token and user on successful register', async () => {
      mockedApi.register.mockResolvedValue({
        access_token: 'new-token',
        token_type: 'bearer',
        user_id: 'u2',
        role: 'user',
      })
      mockedApi.me.mockResolvedValue({
        id: 'u2',
        email: 'new@test.com',
        display_name: 'New User',
        role: 'user',
        is_active: true,
      })

      await useAuthStore.getState().register('new@test.com', 'pass', 'New User')

      const state = useAuthStore.getState()
      expect(state.status).toBe('authenticated')
      expect(state.token).toBe('new-token')
      expect(state.user?.display_name).toBe('New User')
      expect(localStorage.getItem('duh_token')).toBe('new-token')
    })

    it('sets error on failed register', async () => {
      mockedApi.register.mockRejectedValue(new Error('Email already registered'))

      await useAuthStore.getState().register('dup@test.com', 'pass', 'Dup')

      const state = useAuthStore.getState()
      expect(state.status).toBe('error')
      expect(state.error).toBe('Email already registered')
    })
  })

  describe('logout', () => {
    it('clears token and user', () => {
      useAuthStore.setState({
        token: 'some-token',
        user: { id: 'u1', email: 'x@x.com', display_name: 'X', role: 'user', is_active: true },
        status: 'authenticated',
      })
      localStorage.setItem('duh_token', 'some-token')

      useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.token).toBeNull()
      expect(state.user).toBeNull()
      expect(state.status).toBe('idle')
      expect(localStorage.getItem('duh_token')).toBeNull()
    })
  })

  describe('initialize', () => {
    it('sets guest user when auth not required (dev mode)', async () => {
      mockedApi.authStatus.mockResolvedValue({ auth_required: false })

      await useAuthStore.getState().initialize()

      const state = useAuthStore.getState()
      expect(state.authRequired).toBe(false)
      expect(state.status).toBe('authenticated')
      expect(state.user?.id).toBe('guest')
    })

    it('validates existing token when auth required', async () => {
      localStorage.setItem('duh_token', 'existing-token')
      mockedApi.authStatus.mockResolvedValue({ auth_required: true })
      mockedApi.me.mockResolvedValue({
        id: 'u1',
        email: 'test@test.com',
        display_name: 'Test',
        role: 'user',
        is_active: true,
      })

      await useAuthStore.getState().initialize()

      const state = useAuthStore.getState()
      expect(state.authRequired).toBe(true)
      expect(state.status).toBe('authenticated')
      expect(state.user?.email).toBe('test@test.com')
    })

    it('clears invalid token and sets idle', async () => {
      localStorage.setItem('duh_token', 'expired-token')
      mockedApi.authStatus.mockResolvedValue({ auth_required: true })
      mockedApi.me.mockRejectedValue(new Error('Token expired'))

      await useAuthStore.getState().initialize()

      const state = useAuthStore.getState()
      expect(state.status).toBe('idle')
      expect(state.token).toBeNull()
      expect(localStorage.getItem('duh_token')).toBeNull()
    })

    it('sets idle when auth required but no token', async () => {
      mockedApi.authStatus.mockResolvedValue({ auth_required: true })

      await useAuthStore.getState().initialize()

      const state = useAuthStore.getState()
      expect(state.authRequired).toBe(true)
      expect(state.status).toBe('idle')
    })

    it('falls back to guest when auth status endpoint fails', async () => {
      mockedApi.authStatus.mockRejectedValue(new Error('Not found'))

      await useAuthStore.getState().initialize()

      const state = useAuthStore.getState()
      expect(state.authRequired).toBe(false)
      expect(state.status).toBe('authenticated')
      expect(state.user?.id).toBe('guest')
    })
  })
})
