import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchApplicants, LEADER_PAGE_SIZE } from '../../../api/person'
import { t } from '../../../i18n'
import { LEADER_PERSON } from '../../../portals/config'
import { formatDate } from '../../../shared/dates'
import { Alert, Badge, Pager, QueryBoundary } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'
import AdmitControls from './AdmitControls'

/** The people waiting in the leader's scope, the most vouched first, with admit and decline. */
export default function Applicants() {
  usePageTitle(t('leader.applicants.title'))
  const [page, setPage] = useState(1)
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['applicants', page],
    queryFn: () => fetchApplicants(page),
    refetchInterval: 60_000,
  })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('leader.applicants.title')}</h1>
        <p className="lead">{t('leader.applicants.lead')}</p>
        {done && <Alert kind="success">{done}</Alert>}
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('leader.applicants.none')}</p>
            ) : (
              <>
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id}>
                      <h2>{row.full_name}</h2>
                      {row.status === 'searcher' && (
                        <p>
                          <Badge tone="neutral">{t('leader.upgrade.badge')}</Badge>
                        </p>
                      )}
                      <p>
                        {t('leader.applicant.goal', {
                          goal: t(`vouch.page.goal.${row.requested_status ?? 'searcher'}`),
                        })}
                        {' · '}
                        {t('leader.applicant.group', { group: row.home_group.name })}
                        {' · '}
                        {t('leader.applicant.applied', { date: formatDate(row.applied_at) })}
                      </p>
                      <p>
                        {row.vouch_count === 1
                          ? t('applicant.vouchCount.one')
                          : t('applicant.vouchCount', { count: row.vouch_count })}
                        {row.vouchers.length === 0 && <> · {t('leader.applicant.noVouches')}</>}
                      </p>
                      {row.vouchers.length > 0 && (
                        <ul>
                          {row.vouchers.map((voucher, index) => (
                            <li key={index}>
                              {t('vouch.received.from', {
                                name: voucher.name,
                                church: voucher.church_name,
                              })}
                              {!voucher.live && <> · {t('vouch.received.notCounting')}</>}
                            </li>
                          ))}
                        </ul>
                      )}
                      <p>
                        <Link to={`${LEADER_PERSON}/${row.id}`}>
                          {t('leader.applicant.details', { name: row.full_name })}
                        </Link>
                      </p>
                      <AdmitControls
                        id={row.id}
                        name={row.full_name}
                        canAdmitAsProvider={row.can_admit_as_provider}
                        upgrade={row.status === 'searcher'}
                        onDone={setDone}
                      />
                    </li>
                  ))}
                </ul>
                <Pager
                  page={page}
                  pageSize={LEADER_PAGE_SIZE}
                  total={data.total}
                  onChange={(next) => {
                    setDone(null)
                    setPage(next)
                  }}
                />
              </>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}
