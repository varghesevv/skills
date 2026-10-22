import { Link } from 'react-router-dom'

import { t } from '../../i18n'
import { loginPath } from '../../portals/config'
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
          {t('login.noAccount')} <Link to="/register/organisation">{t('nav.register')}</Link>
        </p>
        <p className="auth-links">
          {t('login.otherPeople')} <Link to={loginPath('freelancer')}>{t('login.otherPeopleLink')}</Link>
        </p>
      </div>
    </div>
  )
}
