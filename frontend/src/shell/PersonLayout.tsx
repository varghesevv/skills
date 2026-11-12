import { Link, Outlet } from 'react-router-dom'

import { useAuth, usePerson } from '../auth/AuthContext'
import { t } from '../i18n'
import { PERSON_HOME } from '../portals/config'

/** The signed-in frame of a person of the church trust model: a top bar with sign out. */
export default function PersonLayout() {
  const person = usePerson()
  const { signOut } = useAuth()
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
