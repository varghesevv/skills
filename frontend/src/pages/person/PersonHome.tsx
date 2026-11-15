import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { applyForProvider } from '../../api/person'
import { useAuth, usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { PERSON_GROUP_REQUESTS, PERSON_MOVES, PERSON_VOUCHES } from '../../portals/config'
import { errorMessage } from '../../shared/errors'
import { takeFlash } from '../../shared/flash'
import { Alert } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import ApplicantHome from './ApplicantHome'
import VouchShare from './VouchShare'

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
  // A page that changed who the person is leaves its outcome here (see MyGroup).
  const [notice] = useState(takeFlash)
  usePageTitle(t('nav.home'))
  return (
    <div className="container">
      <div className="card">
        {notice && (
          <Alert kind="success" focus>
            {notice}
          </Alert>
        )}
        <h1>{t('member.welcome', { name: person.full_name })}</h1>
        <p>{t('member.yourStatus', { status: t(`status.${person.status}`) })}</p>
        <p>
          {person.church.name}
          {person.home_group ? `, ${person.home_group.name}` : ''}
        </p>
        <p>
          <Link to={PERSON_VOUCHES}>{t('vouch.given.link')}</Link>
        </p>
        <p>
          <Link to={PERSON_GROUP_REQUESTS}>{t('groupRequests.link')}</Link>
        </p>
        <p>
          <Link to={PERSON_MOVES}>{t('moves.link')}</Link>
        </p>
        <p className="hint">{t('member.soon')}</p>
      </div>
      {person.status === 'searcher' && <Upgrade />}
    </div>
  )
}

/** A searcher can ask to offer their skills. After asking they share a vouch link and see the
 *  vouches, like an applicant, and keep searching. */
function Upgrade() {
  const person = usePerson()
  const { setPerson } = useAuth()
  const apply = useMutation({
    mutationFn: applyForProvider,
    onSuccess: (updated) => setPerson(updated),
  })
  if (person.requested_status === 'provider') {
    return (
      <>
        <section className="card" aria-labelledby="upgrade-waiting">
          <h2 id="upgrade-waiting">{t('upgrade.waiting.title')}</h2>
          <p>
            {person.vouch_count === 1
              ? t('upgrade.waiting.one')
              : t('upgrade.waiting', { count: person.vouch_count })}
          </p>
        </section>
        <VouchShare />
      </>
    )
  }
  return (
    <section className="card" aria-labelledby="upgrade-title">
      <h2 id="upgrade-title">{t('upgrade.title')}</h2>
      <p>{t('upgrade.text')}</p>
      {apply.isError && (
        <Alert kind="error" focus>
          {errorMessage(apply.error)}
        </Alert>
      )}
      <button
        type="button"
        className="btn btn-primary"
        disabled={apply.isPending}
        onClick={() => apply.mutate()}
      >
        {apply.isPending ? t('upgrade.working') : t('upgrade.apply')}
      </button>
    </section>
  )
}
