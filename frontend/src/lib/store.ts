/**
 * DataShield OSINT - Zustand Auth Store
 * Global auth state management
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string | null
  role: 'individual' | 'organization' | 'admin'
  status: string
  mfa_enabled: boolean
  email_verified: boolean
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  accessToken: string | null
  refreshToken: string | null

  // Actions
  setTokens: (access: string, refresh: string) => void
  setUser: (user: User) => void
  logout: () => void
  isAdmin: () => boolean
  isOrganization: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,

      setTokens: (access, refresh) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', access)
          localStorage.setItem('refresh_token', refresh)
        }
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true })
      },

      setUser: (user) => set({ user }),

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user_role')
        }
        set({ user: null, isAuthenticated: false, accessToken: null, refreshToken: null })
      },

      isAdmin: () => get().user?.role === 'admin',
      isOrganization: () =>
        get().user?.role === 'organization' || get().user?.role === 'admin',
    }),
    {
      name: 'datashield-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

// ── Scan store for polling ────────────────────────────────────────────────────
interface ScanState {
  activeScanId: string | null
  setActiveScan: (id: string | null) => void
}

export const useScanStore = create<ScanState>((set) => ({
  activeScanId: null,
  setActiveScan: (id) => set({ activeScanId: id }),
}))
