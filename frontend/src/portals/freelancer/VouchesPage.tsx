import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { decideVouch, listVouches } from '../../api/freelancer'
import type { Vouch, VouchStatus } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, Badge, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

const KEY = ['freelancer', 'vouches'] as const

const STATUS_TEXT: Record<VouchStatus, StringKey> = {
  pending: 'vouches.status.pending',
  approved: 'vouches.status.approved',
  revoked: 'vouches.status.revoked',
}
const STATUS_TONE: Record<VouchStatus, 'neutral' | 'good' | 'warn'> = {
  pending: 'warn',
  approved: 'good',
  revoked: 'neutral',
}

function VouchRow({ vouch }: { vouch: Vouch }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const decide = useMutation({
    mutationFn: (decision: 'accept' | 'reject') => decideVouch(vouch.org_id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
    onError: (failure) => setError(errorMessage(failure)),
  })

  return (
    <li className="card">
      <div className="vouch-head">
        <h2>{vouch.org_name}</h2>
        <Badge tone={STATUS_TONE[vouch.status]}>{t(STATUS_TEXT[vouch.status])}</Badge>
      </div>
      <p className="muted">{t('vouches.since', { date: formatDate(vouch.created_at) })}</p>
      {error && <Alert kind="error">{error}</Alert>}
      {vouch.status === 'pending' && (
        <div className="row-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={decide.isPending}
            onClick={() => decide.mutate('accept')}
            aria-label={`${t('vouches.accept')}: ${vouch.org_name}`}
          >
            {t('vouches.accept')}
          </button>
          <button
            type="button"
            className="btn btn-quiet"
            disabled={decide.isPending}
            onClick={() => decide.mutate('reject')}
            aria-label={`${t('vouches.reject')}: ${vouch.org_name}`}
          >
            {t('vouches.reject')}
          </button>
        </div>
      )}
    </li>
  )
}

export default function VouchesPage() {
  usePageTitle(t('vouches.title'))
  const query = useQuery({ queryKey: KEY, queryFn: listVouches })
  return (
    <>
      <h1>{t('vouches.title')}</h1>
      <p className="lead">{t('vouches.lead')}</p>
      <QueryBoundary query={query}>
        {(vouches) =>
          vouches.length === 0 ? (
            <p className="muted">{t('vouches.empty')}</p>
          ) : (
            <ul className="stack plain-list">
              {vouches.map((vouch) => (
                <VouchRow key={vouch.org_id} vouch={vouch} />
              ))}
            </ul>
          )
        }
      </QueryBoundary>
    </>
  )
}
