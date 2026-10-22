import { useQuery } from '@tanstack/react-query'

import { listOrganisations } from '../../api/workhost'
import { listReports } from '../../api/reports'
import { t } from '../../i18n'
import { ReportCard } from '../../shared/ReportCard'
import { QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { ADMIN_REPORTS_KEY } from './keys'

export default function AdminReportsPage() {
  usePageTitle(t('adminReports.title'))
  const query = useQuery({ queryKey: ADMIN_REPORTS_KEY, queryFn: listReports })
  // Only needed for the organisation filter; the reports still work without it.
  const organisations = useQuery({ queryKey: ['organisations'], queryFn: listOrganisations })
  return (
    <>
      <h1>{t('adminReports.title')}</h1>
      <p className="lead">{t('adminReports.lead')}</p>
      <QueryBoundary query={query}>
        {(reports) => (
          <div className="stack">
            {reports.map((report) => (
              <ReportCard
                key={report.name}
                report={report}
                withFilters
                organisations={organisations.data ?? []}
              />
            ))}
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
