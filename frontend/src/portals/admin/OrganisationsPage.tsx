import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ORGS_PAGE_SIZE, decideOrganisation, listOrganisationsByStatus } from '../../api/admin'
import type { ApprovalStatus, OrgSummary } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, Pager, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { ADMIN_ORGS_KEY } from './keys'

const TABS: { status: ApprovalStatus; label: StringKey }[] = [
  { status: 'pending', label: 'adminOrgs.pending' },
  { status: 'approved', label: 'adminOrgs.approved' },
  { status: 'rejected', label: 'adminOrgs.rejected' },
]

function OrgCard({ org }: { org: OrgSummary }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const decide = useMutation({
    mutationFn: (decision: 'approve' | 'reject') => decideOrganisation(org.id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_ORGS_KEY }),
    onError: (failure) => setError(errorMessage(failure)),
  })
  const canApprove = org.approval_status !== 'approved'
  const canReject = org.approval_status !== 'rejected'

  return (
    <li className="card">
      <h2>{org.org_name}</h2>
      <dl className="facts">
        <div>
          <dt>{t('dashboard.email')}</dt>
          <dd>{org.email}</dd>
        </div>
        <div>
          <dt>{t('dashboard.mobile')}</dt>
          <dd>{org.mobile_number}</dd>
        </div>
        <div>
          <dt>{t('adminOrgs.registered')}</dt>
          <dd>{formatDate(org.created_at)}</dd>
        </div>
      </dl>
      {error && <Alert kind="error">{error}</Alert>}
      <div className="row-actions">
        {canApprove && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={decide.isPending}
            onClick={() => {
              setError(null)
              decide.mutate('approve')
            }}
            aria-label={`${t('adminOrgs.approve')}: ${org.org_name}`}
          >
            {t('adminOrgs.approve')}
          </button>
        )}
        {canReject && (
          <button
            type="button"
            className="btn btn-quiet"
            disabled={decide.isPending}
            onClick={() => {
              setError(null)
              decide.mutate('reject')
            }}
            aria-label={`${t('adminOrgs.reject')}: ${org.org_name}`}
          >
            {t('adminOrgs.reject')}
          </button>
        )}
      </div>
    </li>
  )
}

export default function AdminOrganisationsPage() {
  usePageTitle(t('adminOrgs.title'))
  const [status, setStatus] = useState<ApprovalStatus>('pending')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: [...ADMIN_ORGS_KEY, status, page],
    queryFn: () => listOrganisationsByStatus(status, page),
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <h1>{t('adminOrgs.title')}</h1>
      <p className="lead">{t('adminOrgs.lead')}</p>
      <div className="toolbar" role="group" aria-label={t('adminOrgs.show')}>
        {TABS.map((tab) => (
          <button
            key={tab.status}
            type="button"
            className={`btn ${tab.status === status ? 'btn-primary' : 'btn-quiet'}`}
            aria-pressed={tab.status === status}
            onClick={() => {
              setStatus(tab.status)
              setPage(1)
            }}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>
      <QueryBoundary query={query}>
        {(data) =>
          data.total === 0 ? (
            <p className="muted">{t('adminOrgs.empty')}</p>
          ) : (
            <>
              <ul className="stack plain-list">
                {data.items.map((org) => (
                  <OrgCard key={org.id} org={org} />
                ))}
              </ul>
              <Pager
                page={data.page}
                pageSize={ORGS_PAGE_SIZE}
                total={data.total}
                onChange={setPage}
              />
            </>
          )
        }
      </QueryBoundary>
    </>
  )
}
