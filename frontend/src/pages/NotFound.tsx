import { Link } from 'react-router-dom'

import { t } from '../i18n'
import { usePageTitle } from '../shared/usePageTitle'

export default function NotFound() {
  usePageTitle(t('notFound.title'))
  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('notFound.title')}</h1>
        <p>{t('notFound.text')}</p>
        <Link className="btn btn-primary" to="/">
          {t('notFound.back')}
        </Link>
      </div>
    </div>
  )
}
