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

import { fetchMe, logoutRequest } from '../api/auth'
import { personLoginRequest } from '../api/person'
import { onSessionExpired, refreshSession } from '../api/http'
import type { PersonMe } from '../api/types'
import { clearTokens, getRefreshToken, setTokens } from './tokenStore'

type AuthState =
  | { status: 'loading'; user: null }
  | { status: 'anonymous'; user: null }
  | { status: 'authenticated'; user: PersonMe }

type PersonCredentials = { email: string; password: string }

type AuthValue = AuthState & {
  /** The one login of the church trust model (no account type). */
  signInPerson: (credentials: PersonCredentials) => Promise<PersonMe>
  /** Read the person again after a change (status, application). */
  setPerson: (person: PersonMe) => void
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
      let user: PersonMe | null = null
      if (getRefreshToken() && (await refreshSession())) {
        try {
          const me = await fetchMe()
          // A token of an account of the older kind opens nothing here.
          user = me.user_type === 'person' ? me : null
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

  const signInPerson = useCallback(async (credentials: PersonCredentials) => {
    const tokens = await personLoginRequest(credentials)
    setTokens(tokens.access_token, tokens.refresh_token)
    try {
      const user = await fetchMe()
      if (user.user_type !== 'person') throw new Error('Expected a person')
      setState({ status: 'authenticated', user })
      return user
    } catch (error) {
      clearTokens()
      throw error
    }
  }, [])

  const setPerson = useCallback((person: PersonMe) => {
    setState({ status: 'authenticated', user: person })
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

  const value = useMemo<AuthValue>(
    () => ({ ...state, signInPerson, setPerson, signOut }),
    [state, signInPerson, setPerson, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

/** The signed-in person. Only call this below RequireAuth. */
export function usePerson(): PersonMe {
  const { user } = useAuth()
  if (!user) throw new Error('usePerson needs a signed-in person')
  return user
}
