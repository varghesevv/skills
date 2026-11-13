import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import {
  RequireAuth,
  RequireLeader,
  RequireOlderAccount,
  RequirePerson,
  RequireRole,
} from './auth/guards'
import ForgotPassword from './pages/ForgotPassword'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'
import Login from './pages/Login'
import AdminLogin from './pages/login/AdminLogin'
import OrganisationLogin from './pages/login/OrganisationLogin'
import NotFound from './pages/NotFound'
import Register, { RegisterChoice } from './pages/Register'
import Applicants from './pages/person/leader/Applicants'
import Members from './pages/person/leader/Members'
import PersonDetail from './pages/person/leader/PersonDetail'
import MyVouches from './pages/person/MyVouches'
import Notifications from './pages/person/Notifications'
import PersonHome from './pages/person/PersonHome'
import PersonSignIn from './pages/person/PersonSignIn'
import SignUp from './pages/person/SignUp'
import VouchPage from './pages/person/VouchPage'
import ResetPassword from './pages/ResetPassword'
import {
  LEADER_APPLICANTS,
  LEADER_MEMBERS,
  LEADER_PERSON,
  PERSON_HOME,
  PERSON_NOTIFICATIONS,
  PERSON_SIGN_IN,
  PERSON_SIGN_UP,
  PERSON_VOUCHES,
  PORTALS,
} from './portals/config'
import { freelancerRoutes } from './portals/freelancer/routes'
import { adminRoutes } from './portals/admin/routes'
import { organisationRoutes } from './portals/organisation/routes'
import { workhostRoutes } from './portals/workhost/routes'
import { slugOf } from './terminology/terms'
import AppShell from './shell/AppShell'
import PersonLayout from './shell/PersonLayout'
import PublicLayout from './shell/PublicLayout'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="login" element={<Login />} />
          <Route
            path={`login/${slugOf('freelancer')}`}
            element={<Navigate to="/login" replace />}
          />
          <Route path={`login/${slugOf('workhost')}`} element={<Login userType="workhost" />} />
          <Route path={`login/${slugOf('organisation')}`} element={<OrganisationLogin />} />
          <Route path="login/admin" element={<AdminLogin />} />
          <Route path="register" element={<RegisterChoice />} />
          <Route path="register/:type" element={<Register />} />
          <Route path={PERSON_SIGN_IN.slice(1)} element={<PersonSignIn />} />
          <Route path={PERSON_SIGN_UP.slice(1)} element={<SignUp />} />
          <Route path="join/:token" element={<SignUp />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route element={<RequirePerson />}>
            <Route element={<PersonLayout />}>
              <Route path={PERSON_HOME.slice(1)} element={<PersonHome />} />
              <Route path={PERSON_VOUCHES.slice(1)} element={<MyVouches />} />
              <Route path={PERSON_NOTIFICATIONS.slice(1)} element={<Notifications />} />
              <Route path="vouch/:token" element={<VouchPage />} />
              <Route element={<RequireLeader />}>
                <Route path={LEADER_APPLICANTS.slice(1)} element={<Applicants />} />
                <Route path={LEADER_MEMBERS.slice(1)} element={<Members />} />
                <Route path={`${LEADER_PERSON.slice(1)}/:id`} element={<PersonDetail />} />
              </Route>
            </Route>
          </Route>
          <Route element={<RequireOlderAccount />}>
            <Route element={<AppShell />}>
              {PORTALS.map((portal) => (
                <Route
                  key={portal.path}
                  path={portal.path}
                  element={<RequireRole role={portal.userType} />}
                >
                  <Route index element={<Dashboard />} />
                  {portal.userType === 'freelancer' && freelancerRoutes}
                  {portal.userType === 'workhost' && workhostRoutes}
                  {portal.userType === 'organisation' && organisationRoutes}
                  {portal.userType === 'admin' && adminRoutes}
                </Route>
              ))}
            </Route>
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
