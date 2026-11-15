import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import {
  RequireAuth,
  RequireAdmin,
  RequireLeader,
  RequireOpenAccount,
  RequireOwner,
  RequireProvider,
  RequireSearcher,
} from './auth/guards'
import ForgotPassword from './pages/ForgotPassword'
import Landing from './pages/Landing'
import Privacy from './pages/Privacy'
import NotFound from './pages/NotFound'
import Applicants from './pages/person/leader/Applicants'
import MyGroup from './pages/person/leader/MyGroup'
import Account from './pages/person/Account'
import Downloads from './pages/person/Downloads'
import AdminLabelsPage from './pages/person/owner/Labels'
import AvailabilityPage from './pages/person/provider/AvailabilityPage'
import Frame from './pages/person/provider/Frame'
import LabelsPage from './pages/person/provider/LabelsPage'
import ProfilePage from './pages/person/provider/ProfilePage'
import ProviderPage from './pages/person/search/ProviderPage'
import RatingsGiven from './pages/person/search/RatingsGiven'
import SearchPage from './pages/person/search/SearchPage'
import MyRatings from './pages/person/provider/MyRatings'
import GroupInvitations from './pages/person/leader/GroupInvitations'
import Reports from './pages/person/owner/reports/Reports'
import RunsPage from './pages/person/owner/reports/RunsPage'
import SchedulesPage from './pages/person/owner/reports/SchedulesPage'
import HandoverPage from './pages/person/owner/Handover'
import Views from './pages/person/owner/Views'
import Churches from './pages/person/owner/Churches'
import Groups from './pages/person/leader/Groups'
import Flagged from './pages/person/leader/Flagged'
import AcceptInvitation from './pages/person/AcceptInvitation'
import Moves from './pages/person/Moves'
import GroupRequests from './pages/person/GroupRequests'
import Members from './pages/person/leader/Members'
import PersonDetail from './pages/person/leader/PersonDetail'
import Revoked from './pages/person/leader/Revoked'
import MyVouches from './pages/person/MyVouches'
import Notifications from './pages/person/Notifications'
import PersonHome from './pages/person/PersonHome'
import PersonSignIn from './pages/person/PersonSignIn'
import SignUp from './pages/person/SignUp'
import VouchPage from './pages/person/VouchPage'
import ResetPassword from './pages/ResetPassword'
import {
  LEADER_APPLICANTS,
  ADMIN_GROUPS,
  OWNER_CHURCHES,
  OWNER_HANDOVER,
  OWNER_VIEWS,
  LEADER_GROUP,
  LEADER_INVITATIONS,
  ADMIN_REPORTS,
  OWNER_LABELS,
  OWNER_REPORT_HISTORY,
  OWNER_REPORT_SCHEDULES,
  PERSON_ACCOUNT,
  PERSON_DOWNLOADS,
  PERSON_AVAILABILITY,
  PERSON_PROFILE,
  PERSON_PROVIDERS,
  PERSON_RATINGS,
  PERSON_RATINGS_GIVEN,
  PERSON_SEARCH,
  PERSON_SKILLS,
  LEADER_FLAGGED,
  LEADER_MEMBERS,
  LEADER_REVOKED,
  LEADER_PERSON,
  PERSON_GROUP_REQUESTS,
  PERSON_MOVES,
  PERSON_HOME,
  PERSON_NOTIFICATIONS,
  PERSON_SIGN_IN,
  PERSON_SIGN_UP,
  PRIVACY,
  PERSON_VOUCHES,
} from './portals/config'
import PersonLayout from './shell/PersonLayout'
import PublicLayout from './shell/PublicLayout'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="login/*" element={<Navigate to={PERSON_SIGN_IN} replace />} />
          <Route path="register/*" element={<Navigate to={PERSON_SIGN_UP} replace />} />
          <Route path={PERSON_SIGN_IN.slice(1)} element={<PersonSignIn />} />
          <Route path={PERSON_SIGN_UP.slice(1)} element={<SignUp />} />
          <Route path="join/:token" element={<SignUp />} />
          <Route path="invite/:token" element={<AcceptInvitation />} />
          <Route path={PRIVACY.slice(1)} element={<Privacy />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route element={<PersonLayout />}>
            <Route path={PERSON_HOME.slice(1)} element={<PersonHome />} />
            <Route path={PERSON_GROUP_REQUESTS.slice(1)} element={<GroupRequests />} />
            <Route path={PERSON_MOVES.slice(1)} element={<Moves />} />
            <Route path={PERSON_VOUCHES.slice(1)} element={<MyVouches />} />
            <Route path={PERSON_NOTIFICATIONS.slice(1)} element={<Notifications />} />
            <Route path="vouch/:token" element={<VouchPage />} />
            <Route element={<RequireOpenAccount />}>
              <Route path={PERSON_ACCOUNT.slice(1)} element={<Account />} />
              <Route path={PERSON_DOWNLOADS.slice(1)} element={<Downloads />} />
            </Route>
            <Route element={<RequireSearcher />}>
              <Route path={PERSON_SEARCH.slice(1)} element={<SearchPage />} />
              <Route path={`${PERSON_PROVIDERS.slice(1)}/:id`} element={<ProviderPage />} />
              <Route path={PERSON_RATINGS_GIVEN.slice(1)} element={<RatingsGiven />} />
            </Route>
            <Route element={<RequireProvider />}>
              <Route element={<Frame />}>
                <Route path={PERSON_PROFILE.slice(1)} element={<ProfilePage />} />
                <Route path={PERSON_SKILLS.slice(1)} element={<LabelsPage />} />
                <Route path={PERSON_AVAILABILITY.slice(1)} element={<AvailabilityPage />} />
              </Route>
              <Route path={PERSON_RATINGS.slice(1)} element={<MyRatings />} />
            </Route>
            <Route element={<RequireLeader />}>
              <Route path={OWNER_LABELS.slice(1)} element={<RequireOwner />}>
                <Route
                  index
                  element={
                    <Frame>
                      <AdminLabelsPage />
                    </Frame>
                  }
                />
              </Route>
              <Route path={LEADER_APPLICANTS.slice(1)} element={<Applicants />} />
              <Route path={LEADER_MEMBERS.slice(1)} element={<Members />} />
              <Route path={ADMIN_GROUPS.slice(1)} element={<RequireAdmin />}>
                <Route index element={<Groups />} />
              </Route>
              <Route path={OWNER_HANDOVER.slice(1)} element={<RequireAdmin />}>
                <Route index element={<HandoverPage />} />
              </Route>
              <Route path={ADMIN_REPORTS.slice(1)} element={<RequireAdmin />}>
                <Route index element={<Reports />} />
              </Route>
              <Route path={OWNER_REPORT_HISTORY.slice(1)} element={<RequireOwner />}>
                <Route
                  index
                  element={
                    <Frame>
                      <RunsPage />
                    </Frame>
                  }
                />
              </Route>
              <Route path={OWNER_REPORT_SCHEDULES.slice(1)} element={<RequireOwner />}>
                <Route
                  index
                  element={
                    <Frame>
                      <SchedulesPage />
                    </Frame>
                  }
                />
              </Route>
              <Route path={OWNER_VIEWS.slice(1)} element={<RequireOwner />}>
                <Route index element={<Views />} />
              </Route>
              <Route path={OWNER_CHURCHES.slice(1)} element={<RequireOwner />}>
                <Route index element={<Churches />} />
              </Route>
              <Route path={LEADER_GROUP.slice(1)} element={<MyGroup />} />
              <Route path={LEADER_INVITATIONS.slice(1)} element={<GroupInvitations />} />
              <Route path={LEADER_FLAGGED.slice(1)} element={<Flagged />} />
              <Route path={LEADER_REVOKED.slice(1)} element={<Revoked />} />
              <Route path={`${LEADER_PERSON.slice(1)}/:id`} element={<PersonDetail />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
