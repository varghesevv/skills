import { Route } from 'react-router-dom'

import AdminLabelsPage from './AdminLabelsPage'
import AdminOrganisationsPage from './OrganisationsPage'

// Child routes of /admin (the index route is the shared dashboard).
export const adminRoutes = [
  <Route key="orgs" path="organisations" element={<AdminOrganisationsPage />} />,
  <Route key="labels" path="labels" element={<AdminLabelsPage />} />,
]
