import { Route } from 'react-router-dom'

import { term } from '../../terminology/terms'
import FreelancerDetailPage from '../workhost/FreelancerDetailPage'
import SearchPage from '../workhost/SearchPage'
import OrgProfilePage from './OrgProfilePage'
import ReportsPage from './ReportsPage'
import VouchedPage from './VouchedPage'

// Child routes of /organisation (the index route is the shared dashboard).
// The search and detail pages are the work host ones, with a vouch action instead of a rating form.
export const organisationRoutes = [
  <Route key="freelancers" path={term('freelancers_path')} element={<VouchedPage />} />,
  <Route key="search" path="search" element={<SearchPage portal="organisation" />} />,
  <Route
    key="detail"
    path={`${term('freelancers_path')}/:id`}
    element={<FreelancerDetailPage portal="organisation" />}
  />,
  <Route key="reports" path="reports" element={<ReportsPage />} />,
  <Route key="profile" path="profile" element={<OrgProfilePage />} />,
]
