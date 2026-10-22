import { Link } from 'react-router-dom'

import { useUser } from '../auth/AuthContext'
import { t } from '../i18n'
import { portalFor } from '../portals/config'
import { usePageTitle } from '../shared/usePageTitle'

export default function Dashboard() {
  const user = useUser()
  const portal = portalFor(user.user_type)
  usePageTitle(t('dashboard.title'))
  const shortcuts = portal.nav.filter((item) => !item.end)
  const since = new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' })
  return (
    <>
      <h1>{t('dashboard.welcome', { name: user.org_name ?? user.full_name ?? user.email })}</h1>
      <p className="lead">{t(portal.leadKey)}</p>
      <section className="card" aria-labelledby="account-heading">
        <h2 id="account-heading">{t('dashboard.account')}</h2>
        <dl className="facts">
          {(user.org_name ?? user.full_name) && (
            <div>
              <dt>{user.org_name ? t('field.orgName') : t('field.fullName')}</dt>
              <dd>{user.org_name ?? user.full_name}</dd>
            </div>
          )}
          <div>
            <dt>{t('dashboard.email')}</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>{t('dashboard.mobile')}</dt>
            <dd>{user.mobile_number}</dd>
          </div>
          <div>
            <dt>{t('dashboard.role')}</dt>
            <dd>{t(portal.roleKey)}</dd>
          </div>
          <div>
            <dt>{t('dashboard.since')}</dt>
            <dd>{since}</dd>
          </div>
        </dl>
      </section>
      {shortcuts.length > 0 && (
        <section aria-labelledby="shortcuts-heading" className="shortcuts">
          <h2 id="shortcuts-heading">{t('dashboard.shortcuts')}</h2>
          <ul className="choice-grid">
            {shortcuts.map((item) => (
              <li key={item.to}>
                <Link className="card shortcut" to={item.to}>
                  {t(item.labelKey)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
