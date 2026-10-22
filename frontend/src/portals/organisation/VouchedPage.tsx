import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { VOUCHED_PAGE_SIZE, listVouched, revokeVouch, vouchFor } from '../../api/organisation'
import type { VouchedFreelancer, VouchStatus } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { portalPath } from '../config'
import { term } from '../../terminology/terms'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, Badge, Pager, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { VOUCHED_KEY } from './keys'

const STATUS_TEXT: Record<VouchStatus, StringKey> = {
  pending: 'vouched.status.pending',
  approved: 'vouched.status.approved',
  revoked: 'vouched.status.revoked',
}
const STATUS_TONE: Record<VouchStatus, 'neutral' | 'good' | 'warn'> = {
  pending: 'warn',
  approved: 'good',
  revoked: 'neutral',
}

function Row({ item }: { item: VouchedFreelancer }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const name = item.full_name ?? t('search.noName')

  const change = useMutation({
    mutationFn: async (): Promise<void> => {
      if (item.status === 'revoked') await vouchFor(item.freelancer_id)
      else await revokeVouch(item.freelancer_id)
    },
    onSuccess: async () => {
      setConfirming(false)
      await queryClient.invalidateQueries({ queryKey: VOUCHED_KEY })
    },
    onError: (failure) => {
      setConfirming(false)
      setError(errorMessage(failure))
    },
  })

  return (
    <li className="card">
      <div className="vouch-head">
        <h2>
          <Link to={portalPath('organisation', term('freelancers_path'), item.freelancer_id)}>
            {name}
          </Link>
        </h2>
        <Badge tone={STATUS_TONE[item.status]}>{t(STATUS_TEXT[item.status])}</Badge>
      </div>
      <p className="muted">
        {[item.nationality, item.primary_language].filter(Boolean).join(' · ')}
        {' · '}
        {t('vouched.since', { date: formatDate(item.created_at) })}
      </p>
      {error && <Alert kind="error">{error}</Alert>}
      <div className="row-actions">
        {item.status === 'revoked' ? (
          <button
            type="button"
            className="btn btn-quiet"
            disabled={change.isPending}
            onClick={() => change.mutate()}
            aria-label={`${t('vouched.again')}: ${name}`}
          >
            {t('vouched.again')}
          </button>
        ) : confirming ? (
          <>
            <button
              type="button"
              className="btn btn-primary"
              disabled={change.isPending}
              onClick={() => change.mutate()}
              aria-label={`${t('vouched.confirm')}: ${name}`}
            >
              {t('vouched.confirm')}
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => setConfirming(true)}
            aria-label={`${t('vouched.revoke')}: ${name}`}
          >
            {t('vouched.revoke')}
          </button>
        )}
      </div>
    </li>
  )
}

export default function VouchedPage() {
  usePageTitle(t('vouched.title'))
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: [...VOUCHED_KEY, page],
    queryFn: () => listVouched(page),
    placeholderData: (previous) => previous,
  })
  return (
    <>
      <h1>{t('vouched.title')}</h1>
      <p className="lead">{t('vouched.lead')}</p>
      <p>
        <Link className="btn btn-primary" to={portalPath('organisation', 'search')}>
          {t('vouched.add')}
        </Link>
      </p>
      <QueryBoundary query={query}>
        {(data) =>
          data.total === 0 ? (
            <p className="muted">{t('vouched.empty')}</p>
          ) : (
            <>
              <ul className="stack plain-list">
                {data.items.map((item) => (
                  <Row key={item.freelancer_id} item={item} />
                ))}
              </ul>
              <Pager
                page={data.page}
                pageSize={VOUCHED_PAGE_SIZE}
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
