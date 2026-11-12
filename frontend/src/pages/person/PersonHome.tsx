import { usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { usePageTitle } from '../../shared/usePageTitle'
import ApplicantHome from './ApplicantHome'

/** What a person sees after signing in depends on their status, read from the server. */
export default function PersonHome() {
  const person = usePerson()
  if (person.status === 'pending') return <ApplicantHome />
  if (person.status === 'revoked') return <RevokedHome />
  return <MemberHome />
}

function RevokedHome() {
  usePageTitle(t('revoked.title'))
  return (
    <div className="container">
      <div className="card">
        <h1>{t('revoked.title')}</h1>
        <p>{t('revoked.text')}</p>
      </div>
    </div>
  )
}

/** Admitted people: the screens for each status arrive in later steps of the roadmap. */
function MemberHome() {
  const person = usePerson()
  usePageTitle(t('nav.home'))
  return (
    <div className="container">
      <div className="card">
        <h1>{t('member.welcome', { name: person.full_name })}</h1>
        <p>{t('member.yourStatus', { status: t(`status.${person.status}`) })}</p>
        <p>
          {person.church.name}
          {person.home_group ? `, ${person.home_group.name}` : ''}
        </p>
        <p className="hint">{t('member.soon')}</p>
      </div>
    </div>
  )
}
