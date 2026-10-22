import { Route } from 'react-router-dom'

import { term } from '../../terminology/terms'
import AdminReportsPage from './AdminReportsPage'
import AdminLabelsPage from './AdminLabelsPage'
import AdminOrganisationsPage from './OrganisationsPage'
import RunsPage from './RunsPage'
import SchedulesPage from './SchedulesPage'

// Child routes of /admin (the index route is the shared dashboard).
export const adminRoutes = [
  <Route key="orgs" path={term('organisations_path')} element={<AdminOrganisationsPage />} />,
  <Route key="reports" path="reports" element={<AdminReportsPage />} />,
  <Route key="runs" path="report-history" element={<RunsPage />} />,
  <Route key="schedules" path="report-schedules" element={<SchedulesPage />} />,
  <Route key="labels" path="labels" element={<AdminLabelsPage />} />,
]
