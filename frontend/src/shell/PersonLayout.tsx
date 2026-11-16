import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { fetchNotifications } from '../api/person'
import { useAuth, usePerson } from '../auth/AuthContext'
import { t } from '../i18n'
import { NOTIFICATIONS_KEY, NOTIFICATIONS_POLL_MS } from '../pages/person/Notifications'
import {
  PERSON_ACCOUNT,
  PERSON_DOWNLOADS,
  PERSON_HOME,
  PERSON_NOTIFICATIONS,
  PERSON_SEARCH,
  PRIVACY,
} from '../portals/config'
import GroupMenu from './GroupMenu'
import { atLeast, navFor, type NavGroup } from './nav'
import { useWide } from './useWide'

/** A name field in the bar: it goes to the provider search with the name filled in. */
function NameSearch({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    navigate(trimmed ? `${PERSON_SEARCH}?${new URLSearchParams({ name: trimmed })}` : PERSON_SEARCH)
    setName('')
    onDone()
  }
  return (
    <form className="gsearch" role="search" onSubmit={submit}>
      <label htmlFor="gsearch-name" className="sr-only">
        {t('nav.searchName')}
      </label>
      <input
        id="gsearch-name"
        type="search"
        name="name"
        value={name}
        autoComplete="off"
        placeholder={t('nav.searchName')}
        onChange={(event) => setName(event.target.value)}
      />
      <button type="submit" className="btn btn-quiet">
        {t('nav.searchGo')}
      </button>
    </form>
  )
}

/** The signed-in frame of a person of the church trust model: a top bar with the groups of links
 *  the person's status allows (docs/design-system.md, section 2.2). */
export default function PersonLayout() {
  const person = usePerson()
  const { signOut } = useAuth()
  const wide = useWide()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const menuButton = useRef<HTMLButtonElement>(null)
  // A revoked person has no access to the list; everyone else is told what is new.
  const notifications = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: fetchNotifications,
    refetchInterval: NOTIFICATIONS_POLL_MS,
    enabled: person.status !== 'revoked',
  })
  const unread = notifications.data?.unread_count ?? 0
  const open = person.status !== 'revoked'
  const groups: NavGroup[] = navFor(person)
  const searcher = atLeast(person, 'searcher')

  // A page change closes the phone's menu.
  useEffect(() => setMenuOpen(false), [location.pathname])

  const accountLinks = [
    ...(open ? [{ to: PERSON_ACCOUNT, label: t('account.link') }] : []),
    ...(open ? [{ to: PERSON_DOWNLOADS, label: t('downloads.link') }] : []),
    { to: PRIVACY, label: t('privacy.link') },
  ]
  const account = { id: 'account', label: t('nav.account'), links: accountLinks }
  const signOutItem = (
    <li>
      <p className="navgroup-email">{person.email}</p>
      <button
        type="button"
        className="btn btn-quiet navgroup-signout"
        onClick={() => void signOut()}
      >
        {t('nav.logOut')}
      </button>
    </li>
  )
  const close = () => setMenuOpen(false)

  const notificationsLink = open && (
    <Link className="btn btn-quiet topbar-notifications" to={PERSON_NOTIFICATIONS}>
      {unread > 0 ? t('notifications.link.unread', { count: unread }) : t('notifications.link')}
    </Link>
  )

  return (
    <div className="public">
      <a className="skip-link" href="#main">
        {t('skip.toContent')}
      </a>
      <header
        className="topbar"
        onKeyDown={(event) => {
          if (event.key === 'Escape' && !wide && menuOpen) {
            setMenuOpen(false)
            menuButton.current?.focus()
          }
        }}
      >
        <Link className="brand" to={PERSON_HOME}>
          {t('app.name')}
        </Link>
        {!wide && notificationsLink}
        {!wide && (
          <button
            type="button"
            ref={menuButton}
            className="btn btn-quiet menu-button"
            aria-expanded={menuOpen}
            aria-controls="site-menu"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {t('nav.menu.open')}
          </button>
        )}
        <div id="site-menu" className="site-menu" data-open={wide || menuOpen}>
          {searcher && location.pathname !== PERSON_SEARCH && <NameSearch onDone={close} />}
          {groups.map((group) =>
            group.inline && wide ? (
              <nav key={group.id} className="topbar-nav" aria-label={group.label}>
                {group.links.map((item) => (
                  <NavLink key={item.to} className="btn btn-quiet" to={item.to}>
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            ) : (
              <nav key={group.id} className="topbar-group" aria-label={group.label}>
                <GroupMenu group={group} panel={!wide} onNavigate={close} />
              </nav>
            ),
          )}
          {wide && notificationsLink}
          <nav className="topbar-group topbar-account" aria-label={t('nav.account')}>
            <GroupMenu group={account} panel={!wide} onNavigate={close}>
              {signOutItem}
            </GroupMenu>
          </nav>
        </div>
      </header>
      <main id="main" className="public-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
