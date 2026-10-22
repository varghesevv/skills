import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { t, type StringKey } from '../i18n'
import type { RegisterType } from '../api/types'
import { homePath, registerPath } from '../portals/config'
import { usePageTitle } from '../shared/usePageTitle'

const CHOICES: readonly { type: RegisterType; title: StringKey; text: StringKey }[] = [
  { type: 'freelancer', title: 'landing.freelancer.title', text: 'landing.freelancer.text' },
  { type: 'workhost', title: 'landing.workhost.title', text: 'landing.workhost.text' },
  {
    type: 'organisation',
    title: 'landing.organisation.title',
    text: 'landing.organisation.text',
  },
]

export default function Landing() {
  const { user } = useAuth()
  usePageTitle(t('nav.home'))
  return (
    <div className="container">
      <section className="hero">
        <h1>{t('landing.title')}</h1>
        <p className="lead">{t('landing.lead')}</p>
        {user && (
          <Link className="btn btn-primary" to={homePath(user.user_type)}>
            {t('landing.toDashboard')}
          </Link>
        )}
      </section>
      {!user && (
        <ul className="choice-grid">
          {CHOICES.map((choice) => (
            <li key={choice.type} className="card">
              <h2>{t(choice.title)}</h2>
              <p>{t(choice.text)}</p>
              <Link className="btn btn-primary" to={registerPath(choice.type)}>
                {t('nav.register')}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
