import { useQuery } from '@tanstack/react-query'

import { listReports } from '../../api/reports'
import { t } from '../../i18n'
import { ReportCard } from '../../shared/ReportCard'
import { QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { REPORTS_KEY } from './keys'

export default function ReportsPage() {
  usePageTitle(t('reports.title'))
  const query = useQuery({ queryKey: REPORTS_KEY, queryFn: listReports })
  return (
    <>
      <h1>{t('reports.title')}</h1>
      <p className="lead">{t('reports.lead')}</p>
      <QueryBoundary query={query}>
        {(reports) => (
          <div className="stack">
            {reports.map((report) => (
              <ReportCard key={report.name} report={report} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
