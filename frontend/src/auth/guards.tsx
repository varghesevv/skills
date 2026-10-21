import { Navigate, Outlet, useLocation } from 'react-router-dom'

import type { UserType } from '../api/types'
import { homePath } from '../portals/config'
import { LoadingScreen } from '../shared/ui'
import { useAuth, useUser } from './AuthContext'

export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingScreen />
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

export function RequireRole({ role }: { role: UserType }) {
  const user = useUser()
  if (user.user_type !== role) return <Navigate to={homePath(user.user_type)} replace />
  return <Outlet />
}
