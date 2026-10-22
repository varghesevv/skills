import { Route } from 'react-router-dom'

import FreelancerDetailPage from './FreelancerDetailPage'
import GivenRatingsPage from './GivenRatingsPage'
import HostProfilePage from './HostProfilePage'
import SearchPage from './SearchPage'

// Child routes of /workhost (the index route is the shared dashboard).
export const workhostRoutes = [
  <Route key="search" path="search" element={<SearchPage />} />,
  <Route key="detail" path="freelancers/:id" element={<FreelancerDetailPage />} />,
  <Route key="given" path="ratings" element={<GivenRatingsPage />} />,
  <Route key="profile" path="profile" element={<HostProfilePage />} />,
]
