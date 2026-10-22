import { Route } from 'react-router-dom'

import AvailabilityPage from './AvailabilityPage'
import LabelsPage from './LabelsPage'
import ProfilePage from './ProfilePage'
import RatingsPage from './RatingsPage'
import VouchesPage from './VouchesPage'

// Child routes of /freelancer (the index route is the shared dashboard).
export const freelancerRoutes = [
  <Route key="profile" path="profile" element={<ProfilePage />} />,
  <Route key="labels" path="labels" element={<LabelsPage />} />,
  <Route key="availability" path="availability" element={<AvailabilityPage />} />,
  <Route key="ratings" path="ratings" element={<RatingsPage />} />,
  <Route key="vouches" path="vouches" element={<VouchesPage />} />,
]
