import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { PERSON_HOME, PERSON_SIGN_IN } from '../portals/config'
import { LoadingScreen } from '../shared/ui'
import { useAuth } from './AuthContext'

/** Everything behind the sign-in: a visitor is sent to sign in and brought back afterwards. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingScreen />
  if (status === 'anonymous') {
    return (
      <Navigate to={PERSON_SIGN_IN} replace state={{ from: location.pathname + location.search }} />
    )
  }
  return <Outlet />
}

/** The screens every person has except one who was revoked, who goes to their home. */
export function RequireOpenAccount() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const open = user.status !== 'revoked'
  return open ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of a SEARCHER, and of everyone above: an applicant goes home. */
export function RequireSearcher() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const searcher = ['searcher', 'provider', 'verifier', 'admin', 'owner'].includes(user.status)
  return searcher ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of a provider, and of everyone above: a SEARCHER or an applicant goes home. */
export function RequireProvider() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const provider = ['provider', 'verifier', 'admin', 'owner'].includes(user.status)
  return provider ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of a leader: VERIFIER, ADMIN or OWNER. Everyone else goes to their own home. */
export function RequireLeader() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const leader = ['verifier', 'admin', 'owner'].includes(user.status)
  return leader ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of an ADMIN or the OWNER. Everyone else goes to their own home. */
export function RequireAdmin() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const admin = ['admin', 'owner'].includes(user.status)
  return admin ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}

/** The screens of the OWNER. Everyone else goes to their own home. */
export function RequireOwner() {
  const { user } = useAuth()
  if (!user) return <LoadingScreen />
  const owner = user.status === 'owner'
  return owner ? <Outlet /> : <Navigate to={PERSON_HOME} replace />
}
