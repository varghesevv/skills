import { Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { RequireAuth, RequireRole } from './auth/guards'
import ForgotPassword from './pages/ForgotPassword'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Register, { RegisterChoice } from './pages/Register'
import ResetPassword from './pages/ResetPassword'
import { PORTALS } from './portals/config'
import AppShell from './shell/AppShell'
import PublicLayout from './shell/PublicLayout'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="login" element={<Login />} />
          <Route path="register" element={<RegisterChoice />} />
          <Route path="register/:type" element={<Register />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            {PORTALS.map((portal) => (
              <Route
                key={portal.path}
                path={portal.path}
                element={<RequireRole role={portal.userType} />}
              >
                <Route index element={<Dashboard />} />
                {/* Later steps add this portal's pages here. */}
              </Route>
            ))}
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
