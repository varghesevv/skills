import { Link } from 'react-router-dom'

import { t } from '../../i18n'
import { registerPath } from '../../portals/config'
import { usePageTitle } from '../../shared/usePageTitle'
import LoginForm from './LoginForm'

/** Log in for organisations only. */
export default function OrganisationLogin() {
  usePageTitle(t('login.org.title'))
  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('login.org.title')}</h1>
        <p>{t('login.org.text')}</p>
        <LoginForm userType="organisation" />
        <p>
          {t('login.noAccount')} <Link to={registerPath('organisation')}>{t('nav.register')}</Link>
        </p>
      </div>
    </div>
  )
}
