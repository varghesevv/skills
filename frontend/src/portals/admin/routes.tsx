import { Route } from 'react-router-dom'

import { term } from '../../terminology/terms'
import AdminLabelsPage from './AdminLabelsPage'
import AdminOrganisationsPage from './OrganisationsPage'

// Child routes of /admin (the index route is the shared dashboard).
export const adminRoutes = [
  <Route key="orgs" path={term('organisations_path')} element={<AdminOrganisationsPage />} />,
  <Route key="labels" path="labels" element={<AdminLabelsPage />} />,
]
