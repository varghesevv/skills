import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth, useUser } from '../auth/AuthContext'
import { t } from '../i18n'
import { portalFor } from '../portals/config'
import { term } from '../terminology/terms'

/**
 * Signed-in layout. Below 1024 px the navigation is a drawer opened from the top bar;
 * from 1024 px it is a permanent column (see styles/global.css).
 */
export default function AppShell() {
  const user = useUser()
  const { signOut } = useAuth()
  const portal = portalFor(user.user_type)
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  const menuButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        menuButton.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        {t('skip.toContent')}
      </a>
      <header className="topbar">
        <button
          ref={menuButton}
          type="button"
          className="icon-btn menu-button"
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen((current) => !current)}
        >
          <span aria-hidden="true">☰</span>
          <span className="sr-only">{t('nav.menu')}</span>
        </button>
        <Link className="brand" to={portal.path}>
          {t('app.name')}
        </Link>
        <div className="topbar-user">
          <span className="topbar-email">{user.email}</span>
          <button type="button" className="btn btn-quiet" onClick={() => void signOut()}>
            {t('nav.logOut')}
          </button>
        </div>
      </header>

      <div className="shell-body">
        <nav id="sidebar" className="sidebar" data-open={open} aria-label={t('nav.main')}>
          <div className="sidebar-head">
            <span className="role-badge">
              {portal.userType === 'admin' ? t(portal.roleKey) : term(`badge_${portal.userType}`)}
            </span>
            <button type="button" className="icon-btn sidebar-close" onClick={() => setOpen(false)}>
              <span aria-hidden="true">✕</span>
              <span className="sr-only">{t('nav.close')}</span>
            </button>
          </div>
          <ul className="nav-list">
            {portal.nav.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.end} className="nav-link">
                  {t(item.labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        {open && <div className="backdrop" aria-hidden="true" onClick={() => setOpen(false)} />}
        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
