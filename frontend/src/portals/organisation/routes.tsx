import { Route } from 'react-router-dom'

import { term } from '../../terminology/terms'
import OrgProfilePage from './OrgProfilePage'
import ReportsPage from './ReportsPage'
import VouchedPage from './VouchedPage'

// Child routes of /organisation (the index route is the shared dashboard). The search and the
// pages of a provider moved to the member pages in S5.5; this portal goes in S5.6.
export const organisationRoutes = [
  <Route key="freelancers" path={term('freelancers_path')} element={<VouchedPage />} />,
  <Route key="reports" path="reports" element={<ReportsPage />} />,
  <Route key="profile" path="profile" element={<OrgProfilePage />} />,
]
