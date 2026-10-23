import { Link, Navigate, useSearchParams } from 'react-router-dom'

import { t } from '../i18n'
import { loginPath, registerPath } from '../portals/config'
import { usePageTitle } from '../shared/usePageTitle'
import LoginForm from './login/LoginForm'
import { isUserType } from './userTypes'

type PeopleType = 'freelancer' | 'workhost'

const PEOPLE: readonly PeopleType[] = ['freelancer', 'workhost']

/** Log in for freelancers and work hosts. Organisations and admins have their own pages. */
export default function Login({ userType = 'freelancer' }: { userType?: PeopleType }) {
  usePageTitle(t('login.title'))
  const [params] = useSearchParams()
  const legacy = params.get('type') // older links looked like /login?type=organisation
  if (isUserType(legacy) && legacy !== userType) {
    return <Navigate to={loginPath(legacy)} replace />
  }

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('login.title')}</h1>
        <nav className="segmented" aria-label={t('login.switch')}>
          {PEOPLE.map((type) => (
            <Link
              key={type}
              to={loginPath(type)}
              aria-current={type === userType ? 'page' : undefined}
            >
              {t(`role.${type}`)}
            </Link>
          ))}
        </nav>
        <LoginForm userType={userType} />
        <p>
          {t('login.noAccount')} <Link to={registerPath(userType)}>{t('nav.register')}</Link>
        </p>
      </div>
    </div>
  )
}
