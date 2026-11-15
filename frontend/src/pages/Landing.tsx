import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { t } from '../i18n'
import { PERSON_HOME, PERSON_SIGN_IN, PERSON_SIGN_UP } from '../portals/config'
import { usePageTitle } from '../shared/usePageTitle'

export default function Landing() {
  const { user } = useAuth()
  usePageTitle(t('nav.home'))
  return (
    <div className="container">
      <section className="hero">
        <h1>{t('landing.title')}</h1>
        <p className="lead">{t('landing.lead')}</p>
        {user && (
          <Link className="btn btn-primary" to={PERSON_HOME}>
            {t('landing.toDashboard')}
          </Link>
        )}
      </section>
      {!user && (
        <section className="card">
          <h2>{t('landing.member.title')}</h2>
          <p>{t('landing.member.text')}</p>
          <p>
            <Link className="btn btn-primary" to={PERSON_SIGN_UP}>
              {t('member.signUp.title')}
            </Link>{' '}
            <Link className="btn btn-quiet" to={PERSON_SIGN_IN}>
              {t('member.signIn.title')}
            </Link>
          </p>
        </section>
      )}
    </div>
  )
}
