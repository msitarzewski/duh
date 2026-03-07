import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'

// ── Mock the API client ──
vi.mock('@/api/client', () => ({
  api: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    authStatus: vi.fn(),
    health: vi.fn(),
  },
}))

import { LoginPage } from '@/pages/LoginPage'
import { ProtectedRoute } from '@/components/shared/ProtectedRoute'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      token: null,
      user: null,
      status: 'idle',
      error: null,
      authRequired: true,
    })
  })

  it('renders login form by default', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Sign In' })).toBeTruthy()
    expect(screen.getByPlaceholderText('you@example.com')).toBeTruthy()
    expect(screen.getByPlaceholderText('\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022')).toBeTruthy()
    expect(screen.getByText('Register')).toBeTruthy()
  })

  it('shows error message when login fails', async () => {
    useAuthStore.setState({
      status: 'error',
      error: 'Invalid credentials',
    })

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('Invalid credentials')).toBeTruthy()
  })

  it('shows display name field in register mode', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    // Click Register link
    const registerLink = screen.getByText('Register')
    act(() => { registerLink.click() })

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Account' })).toBeTruthy()
      expect(screen.getByPlaceholderText('Your name')).toBeTruthy()
    })
  })

  it('redirects when authenticated', () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'u1', email: 'a@b.com', display_name: 'A', role: 'user', is_active: true },
    })

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    // When authenticated, LoginPage renders Navigate to "/"
    // In test env, we just verify the component doesn't render the form
    expect(screen.queryByText('Sign In')).toBeNull()
  })
})

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders children when authenticated', () => {
    useAuthStore.setState({
      status: 'authenticated',
      authRequired: true,
      user: { id: 'u1', email: 'a@b.com', display_name: 'A', role: 'user', is_active: true },
    })

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    )

    expect(screen.getByText('Protected Content')).toBeTruthy()
  })

  it('renders children when auth not required (dev mode)', () => {
    useAuthStore.setState({
      status: 'authenticated',
      authRequired: false,
      user: { id: 'guest', email: '', display_name: 'Guest', role: 'admin', is_active: true },
    })

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Dev Mode Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    )

    expect(screen.getByText('Dev Mode Content')).toBeTruthy()
  })

  it('redirects to login when not authenticated', () => {
    useAuthStore.setState({
      status: 'idle',
      authRequired: true,
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <ProtectedRoute>
          <div>Should Not Show</div>
        </ProtectedRoute>
      </MemoryRouter>,
    )

    expect(screen.queryByText('Should Not Show')).toBeNull()
  })

  it('shows loading skeleton when auth status unknown', () => {
    useAuthStore.setState({
      authRequired: null,
    })

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Should Not Show</div>
        </ProtectedRoute>
      </MemoryRouter>,
    )

    expect(screen.queryByText('Should Not Show')).toBeNull()
  })
})
