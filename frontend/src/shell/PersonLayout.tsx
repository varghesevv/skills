import { useQuery } from '@tanstack/react-query'
import { Link, Outlet } from 'react-router-dom'

import { fetchNotifications } from '../api/person'
import { useAuth, usePerson } from '../auth/AuthContext'
import { leadsOwnGroup } from '../pages/person/leads'
import { t } from '../i18n'
import { NOTIFICATIONS_KEY, NOTIFICATIONS_POLL_MS } from '../pages/person/Notifications'
import {
  ADMIN_GROUPS,
  LEADER_GROUP,
  LEADER_INVITATIONS,
  ADMIN_REPORTS,
  OWNER_LABELS,
  PERSON_ACCOUNT,
  PRIVACY,
  PERSON_DOWNLOADS,
  PERSON_AVAILABILITY,
  PERSON_PROFILE,
  PERSON_RATINGS,
  PERSON_RATINGS_GIVEN,
  PERSON_SEARCH,
  PERSON_SKILLS,
  OWNER_CHURCHES,
  OWNER_HANDOVER,
  OWNER_VIEWS,
  LEADER_APPLICANTS,
  LEADER_FLAGGED,
  LEADER_MEMBERS,
  LEADER_REVOKED,
  PERSON_HOME,
  PERSON_MOVES,
  PERSON_NOTIFICATIONS,
} from '../portals/config'

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
  const leader = ['verifier', 'admin', 'owner'].includes(person.status)
  const admin = person.status === 'admin' || person.status === 'owner'
  const searcher = ['searcher', 'provider', 'verifier', 'admin', 'owner'].includes(person.status)
  const provider = ['provider', 'verifier', 'admin', 'owner'].includes(person.status)
  return (
    <div className="public">
      <a className="skip-link" href="#main">
        {t('skip.toContent')}
      </a>
      <header className="topbar">
        <Link className="brand" to={PERSON_HOME}>
          {t('app.name')}
        </Link>
        {searcher && (
          <nav className="topbar-nav" aria-label={t('member.nav.label')}>
            <Link className="btn btn-quiet" to={PERSON_SEARCH}>
              {t('nav.search')}
            </Link>
            <Link className="btn btn-quiet" to={PERSON_RATINGS_GIVEN}>
              {t('nav.given')}
            </Link>
          </nav>
        )}
        {provider && (
          <nav className="topbar-nav" aria-label={t('provider.nav.label')}>
            <Link className="btn btn-quiet" to={PERSON_PROFILE}>
              {t('nav.profile')}
            </Link>
            <Link className="btn btn-quiet" to={PERSON_SKILLS}>
              {t('nav.labels')}
            </Link>
            <Link className="btn btn-quiet" to={PERSON_AVAILABILITY}>
              {t('nav.availability')}
            </Link>
            <Link className="btn btn-quiet" to={PERSON_RATINGS}>
              {t('nav.ratings')}
            </Link>
          </nav>
        )}
        {leader && (
          <nav className="topbar-nav" aria-label={t('leader.nav.label')}>
            <Link className="btn btn-quiet" to={LEADER_APPLICANTS}>
              {t('leader.nav.applicants')}
            </Link>
            <Link className="btn btn-quiet" to={LEADER_MEMBERS}>
              {t('leader.nav.members')}
            </Link>
            <Link className="btn btn-quiet" to={LEADER_GROUP}>
              {t('leader.nav.group')}
            </Link>
            {leadsOwnGroup(person) && (
              <Link className="btn btn-quiet" to={LEADER_INVITATIONS}>
                {t('invitations.nav')}
              </Link>
            )}
            <Link className="btn btn-quiet" to={PERSON_MOVES}>
              {t('leader.nav.moves')}
            </Link>
            {person.status === 'owner' && (
              <Link className="btn btn-quiet" to={OWNER_VIEWS}>
                {t('owner.nav.views')}
              </Link>
            )}
            {person.status === 'owner' && (
              <Link className="btn btn-quiet" to={OWNER_LABELS}>
                {t('nav.adminLabels')}
              </Link>
            )}
            {person.status === 'owner' && (
              <Link className="btn btn-quiet" to={OWNER_CHURCHES}>
                {t('owner.nav.churches')}
              </Link>
            )}
            {admin && (
              <Link className="btn btn-quiet" to={ADMIN_REPORTS}>
                {t('nav.reports')}
              </Link>
            )}
            {admin && (
              <Link className="btn btn-quiet" to={OWNER_HANDOVER}>
                {t('handover.nav')}
              </Link>
            )}
            {admin && (
              <Link className="btn btn-quiet" to={ADMIN_GROUPS}>
                {t('admin.nav.groups')}
              </Link>
            )}
            <Link className="btn btn-quiet" to={LEADER_FLAGGED}>
              {t('leader.nav.flagged')}
            </Link>
            <Link className="btn btn-quiet" to={LEADER_REVOKED}>
              {t('leader.nav.revoked')}
            </Link>
          </nav>
        )}
        <div className="topbar-user">
          {person.status !== 'revoked' && (
            <Link className="btn btn-quiet" to={PERSON_NOTIFICATIONS}>
              {unread > 0
                ? t('notifications.link.unread', { count: unread })
                : t('notifications.link')}
            </Link>
          )}
          {person.status !== 'revoked' && (
            <Link className="btn btn-quiet" to={PERSON_ACCOUNT}>
              {t('account.link')}
            </Link>
          )}
          <Link className="btn btn-quiet" to={PRIVACY}>
            {t('privacy.link')}
          </Link>
          {person.status !== 'revoked' && (
            <Link className="btn btn-quiet" to={PERSON_DOWNLOADS}>
              {t('downloads.link')}
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
