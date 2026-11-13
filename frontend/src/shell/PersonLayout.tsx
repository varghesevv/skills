import { useQuery } from '@tanstack/react-query'
import { Link, Outlet } from 'react-router-dom'

import { fetchNotifications } from '../api/person'
import { useAuth, usePerson } from '../auth/AuthContext'
import { t } from '../i18n'
import { NOTIFICATIONS_KEY, NOTIFICATIONS_POLL_MS } from '../pages/person/Notifications'
import { PERSON_HOME, PERSON_NOTIFICATIONS } from '../portals/config'

/** The signed-in frame of a person of the church trust model: a top bar with sign out. */
export default function PersonLayout() {
  const person = usePerson()
  const { signOut } = useAuth()
  // A revoked person has no access to the list; everyone else is told what is new.
  const notifications = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: fetchNotifications,
    refetchInterval: NOTIFICATIONS_POLL_MS,
    enabled: person.status !== 'revoked',
  })
  const unread = notifications.data?.unread_count ?? 0
  return (
    <div className="public">
      <a className="skip-link" href="#main">
        {t('skip.toContent')}
      </a>
      <header className="topbar">
        <Link className="brand" to={PERSON_HOME}>
          {t('app.name')}
        </Link>
        <div className="topbar-user">
          {person.status !== 'revoked' && (
            <Link className="btn btn-quiet" to={PERSON_NOTIFICATIONS}>
              {unread > 0
                ? t('notifications.link.unread', { count: unread })
                : t('notifications.link')}
            </Link>
          )}
          <span className="topbar-email">{person.email}</span>
          <button type="button" className="btn btn-quiet" onClick={() => void signOut()}>
            {t('nav.logOut')}
          </button>
        </div>
      </header>
      <main id="main" className="public-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
