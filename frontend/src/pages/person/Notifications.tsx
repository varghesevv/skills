import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/person'
import type { NotificationItem } from '../../api/types'
import { usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { PERSON_HOME } from '../../portals/config'
import { formatDateTime } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

export const NOTIFICATIONS_KEY = ['notifications'] as const
/** Clients ask again every minute while open (decision D-18). */
export const NOTIFICATIONS_POLL_MS = 60_000

/** One line for a notification, from its kind and the person it is about. */
export function notificationText(item: NotificationItem): string {
  const name = item.subject?.name || t('notifications.someone')
  switch (item.kind) {
    case 'applicant_new':
      return t('notifications.applicant_new', { name })
    case 'vouch_received':
      return t('notifications.vouch_received', { name })
    case 'provider_application':
      return t('notifications.provider_application', { name })
    case 'provider_declined':
      return t('notifications.provider_declined', { name })
    case 'admitted':
      return t('notifications.admitted', { name })
    default:
      return t('notifications.unknown')
  }
}

export default function Notifications() {
  usePageTitle(t('notifications.title'))
  const queryClient = useQueryClient()
  const revoked = usePerson().status === 'revoked'
  const list = useQuery({
    enabled: !revoked,
    queryKey: NOTIFICATIONS_KEY,
    queryFn: fetchNotifications,
    refetchInterval: NOTIFICATIONS_POLL_MS,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })
  const readOne = useMutation({ mutationFn: markNotificationRead, onSettled: refresh })
  const readAll = useMutation({ mutationFn: markAllNotificationsRead, onSettled: refresh })
  const failure = readOne.error ?? readAll.error
  if (revoked) return <Navigate to={PERSON_HOME} replace />

  return (
    <div className="container">
      <div className="card">
        <h1>{t('notifications.title')}</h1>
        {failure && (
          <Alert kind="error" focus>
            {errorMessage(failure)}
          </Alert>
        )}
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('notifications.none')}</p>
            ) : (
              <>
                {data.unread_count > 0 && (
                  <button
                    type="button"
                    className="btn btn-quiet"
                    disabled={readAll.isPending}
                    onClick={() => readAll.mutate()}
                  >
                    {t('notifications.readAll')}
                  </button>
                )}
                <ul className="plain-list">
                  {data.items.map((item) => (
                    <li key={item.id}>
                      {!item.read && <strong>{t('notifications.unread')} · </strong>}
                      {notificationText(item)}
                      {' · '}
                      <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
                      {!item.read && (
                        <>
                          {' '}
                          <button
                            type="button"
                            className="btn btn-quiet"
                            aria-label={t('notifications.read.named', {
                              text: notificationText(item),
                            })}
                            disabled={readOne.isPending}
                            onClick={() => readOne.mutate(item.id)}
                          >
                            {t('notifications.read')}
                          </button>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}
