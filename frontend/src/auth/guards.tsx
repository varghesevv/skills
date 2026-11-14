import { Navigate, Outlet, useLocation } from 'react-router-dom'

import type { UserType } from '../api/types'
import {
  homePath,
  loginPathFor,
  PERSON_HOME,
  PERSON_SIGN_IN,
  VOUCH_LINK_PREFIX,
} from '../portals/config'
import { LoadingScreen } from '../shared/ui'
import { useAuth } from './AuthContext'

export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingScreen />
  if (status === 'anonymous') {
    return (
      <Navigate
        to={
          location.pathname.startsWith(PERSON_HOME) ||
          location.pathname.startsWith(VOUCH_LINK_PREFIX)
            ? PERSON_SIGN_IN
            : loginPathFor(location.pathname)
        }
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }
  return <Outlet />
}

export function RequireRole({ role }: { role: UserType }) {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  if (user.user_type === 'person') return <Navigate to={PERSON_HOME} replace />
  if (user.user_type !== role) return <Navigate to={homePath(user.user_type)} replace />
  return <Outlet />
}

/** In front of the portals of the older accounts: a person goes to their own home instead. */
export function RequireOlderAccount() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  if (user.user_type === 'person') return <Navigate to={PERSON_HOME} replace />
  return <Outlet />
}

/** Only people of the church trust model; an older account is sent to its own portal. */
export function RequirePerson() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  if (user.user_type !== 'person') return <Navigate to={homePath(user.user_type)} replace />
  return <Outlet />
}

/** The screens of a leader: VERIFIER, ADMIN or OWNER. Everyone else goes to their own home. */
export function RequireLeader() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const leader = user.user_type === 'person' && ['verifier', 'admin', 'owner'].includes(user.status)
  return leader ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of an ADMIN or the OWNER. Everyone else goes to their own home. */
export function RequireAdmin() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const admin = user.user_type === 'person' && ['admin', 'owner'].includes(user.status)
  return admin ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}
