import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { fetchChurches } from '../../../../api/person'
import { listReports } from '../../../../api/reports'
import { usePerson } from '../../../../auth/AuthContext'
import { t } from '../../../../i18n'
import { OWNER_REPORT_HISTORY, OWNER_REPORT_SCHEDULES } from '../../../../portals/config'
import { ReportCard } from '../../../../shared/ReportCard'
import { QueryBoundary } from '../../../../shared/ui'
import { usePageTitle } from '../../../../shared/usePageTitle'
import { REPORTS_KEY } from './keys'

/** The reports an ADMIN (their own church) or the OWNER (every church, or one) may run. */
export default function Reports() {
  usePageTitle(t('adminReports.title'))
  const person = usePerson()
  const owner = person.status === 'owner'
  const query = useQuery({ queryKey: REPORTS_KEY, queryFn: listReports })
  // Only the OWNER chooses a church, and the reports still work without the list.
  const churches = useQuery({ queryKey: ['churches'], queryFn: fetchChurches, enabled: owner })
  return (
    <div className="container">
      <h1>{t('adminReports.title')}</h1>
      <p className="lead">{owner ? t('adminReports.lead') : t('reports.leadAdmin')}</p>
      {owner && (
        <p>
          <Link to={OWNER_REPORT_HISTORY}>{t('reports.history.link')}</Link>{' '}
          <Link to={OWNER_REPORT_SCHEDULES}>{t('reports.schedules.link')}</Link>
        </p>
      )}
      <QueryBoundary query={query}>
        {(reports) => (
          <div className="stack">
            {reports.map((report) => (
              <ReportCard
                key={report.name}
                report={report}
                withFilters
                churches={owner ? (churches.data?.items ?? []) : []}
              />
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
