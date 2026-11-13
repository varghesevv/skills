import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchVouchesGiven, withdrawVouch } from '../../api/person'
import { t } from '../../i18n'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

/** The vouches a member gave. One can be taken back until the person is admitted. */
export default function MyVouches() {
  usePageTitle(t('vouch.given.title'))
  const queryClient = useQueryClient()
  const given = useQuery({ queryKey: ['vouches-given'], queryFn: fetchVouchesGiven })
  const withdraw = useMutation({
    mutationFn: withdrawVouch,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['vouches-given'] }),
  })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('vouch.given.title')}</h1>
        {withdraw.isError && (
          <Alert kind="error" focus>
            {errorMessage(withdraw.error)}
          </Alert>
        )}
        <QueryBoundary query={given}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('vouch.given.none')}</p>
            ) : (
              <ul className="plain-list">
                {data.items.map((vouch) => (
                  <li key={vouch.id}>
                    {t('vouch.given.status', {
                      name: vouch.applicant_name || t('notifications.someone'),
                      status: vouch.withdrawn
                        ? t('vouch.given.withdrawn')
                        : vouch.can_withdraw
                          ? t('status.pending')
                          : t('vouch.given.decided'),
                    })}
                    {' · '}
                    <time dateTime={vouch.created_at}>{formatDate(vouch.created_at)}</time>
                    {vouch.can_withdraw && !vouch.withdrawn && (
                      <>
                        {' '}
                        <button
                          type="button"
                          className="btn btn-quiet"
                          disabled={withdraw.isPending}
                          onClick={() => withdraw.mutate(vouch.id)}
                        >
                          {t('vouch.given.withdraw', {
                            name: vouch.applicant_name || t('notifications.someone'),
                          })}
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}
