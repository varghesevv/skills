import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { fetchMe, loginRequest, logoutRequest } from '../api/auth'
import { onSessionExpired, refreshSession } from '../api/http'
import type { Me, UserType } from '../api/types'
import { clearTokens, getRefreshToken, setTokens } from './tokenStore'

type AuthState =
  | { status: 'loading'; user: null }
  | { status: 'anonymous'; user: null }
  | { status: 'authenticated'; user: Me }

type Credentials = { email: string; password: string; user_type: UserType }

type AuthValue = AuthState & {
  signIn: (credentials: Credentials) => Promise<Me>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>({ status: 'loading', user: null })

  // The refresh token was rejected somewhere in the app: go back to anonymous.
  useEffect(() => {
    onSessionExpired(() => {
      queryClient.clear()
      setState({ status: 'anonymous', user: null })
    })
    return () => onSessionExpired(null)
  }, [queryClient])

  // On first load, restore the session from the refresh token if there is one.
  useEffect(() => {
    let cancelled = false
    async function restore() {
      let user: Me | null = null
      if (getRefreshToken() && (await refreshSession())) {
        try {
          user = await fetchMe()
        } catch {
          user = null
        }
      }
      if (!cancelled) {
        setState(user ? { status: 'authenticated', user } : { status: 'anonymous', user: null })
      }
    }
    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (credentials: Credentials) => {
    const tokens = await loginRequest(credentials)
    setTokens(tokens.access_token, tokens.refresh_token)
    try {
      const user = await fetchMe()
      setState({ status: 'authenticated', user })
      return user
    } catch (error) {
      clearTokens()
      throw error
    }
  }, [])

  const signOut = useCallback(async () => {
    const refreshToken = getRefreshToken()
    clearTokens()
    setState({ status: 'anonymous', user: null })
    queryClient.clear()
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken)
      } catch {
        // Best effort: the local session is already gone and the token expires on its own.
      }
    }
  }, [queryClient])

  const value = useMemo<AuthValue>(() => ({ ...state, signIn, signOut }), [state, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

/** The signed-in user. Only call this below RequireAuth. */
export function useUser(): Me {
  const { user } = useAuth()
  if (!user) throw new Error('useUser needs a signed-in user')
  return user
}
