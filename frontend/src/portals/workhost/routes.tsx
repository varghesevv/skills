import { Route } from 'react-router-dom'

import HostProfilePage from './HostProfilePage'

// Child routes of /workhost (the index route is the shared dashboard). The search, the pages of
// a provider and the ratings given moved to the member pages in S5.5; this portal goes in S5.6.
export const workhostRoutes = [<Route key="profile" path="profile" element={<HostProfilePage />} />]
