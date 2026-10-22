import { usePageTitle } from '../../shared/usePageTitle'
import { t } from '../../i18n'
import LoginForm from './LoginForm'

/** Log in for administrators only. There is no sign-up: operators create admins. */
export default function AdminLogin() {
  usePageTitle(t('login.admin.title'))
  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('login.admin.title')}</h1>
        <p>{t('login.admin.text')}</p>
        <LoginForm userType="admin" />
      </div>
    </div>
  )
}
