import { Link, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { t } from '../i18n'
import { PERSON_HOME, PERSON_SIGN_IN, PERSON_SIGN_UP } from '../portals/config'

export default function PublicLayout() {
  const { status, user } = useAuth()
  return (
    <div className="public">
      <a className="skip-link" href="#main">
        {t('skip.toContent')}
      </a>
      <header className="topbar">
        <Link className="brand" to="/">
          {t('app.name')}
        </Link>
        <nav className="topbar-user" aria-label={t('nav.main')}>
          {user ? (
            <Link className="btn btn-quiet" to={PERSON_HOME}>
              {t('nav.dashboard')}
            </Link>
          ) : (
            status !== 'loading' && (
              <>
                <Link className="btn btn-quiet" to={PERSON_SIGN_IN}>
                  {t('nav.logIn')}
                </Link>
                <Link className="btn btn-primary" to={PERSON_SIGN_UP}>
                  {t('nav.register')}
                </Link>
              </>
            )
          )}
        </nav>
      </header>
      <main id="main" className="public-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
