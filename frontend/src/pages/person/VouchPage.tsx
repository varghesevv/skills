import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../../api/http'
import { lookupVouchLink, vouchThroughLink } from '../../api/person'
import { usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { PERSON_HOME } from '../../portals/config'
import { errorMessage } from '../../shared/errors'
import { Alert } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

/** What a failed lookup or vouch means for the person, by the code the server answers with. */
function vouchProblem(error: unknown, name: string): string {
  if (error instanceof ApiError) {
    if (error.code === 'cannot_vouch_self') return t('vouch.page.self')
    if (error.code === 'already_vouched') return t('vouch.page.already', { name })
    if (error.code === 'not_found') return t('vouch.page.bad')
    if (error.code === 'rate_limited') return t('vouch.page.limit')
    if (error.code === 'not_admitted') return t('vouch.page.notAdmitted')
  }
  return errorMessage(error)
}

/** The page a vouch link opens: who asks, and one button to vouch. */
export default function VouchPage() {
  usePageTitle(t('vouch.page.title'))
  const { token = '' } = useParams()
  const person = usePerson()
  const admitted = person.status !== 'pending' && person.status !== 'revoked'
  const info = useQuery({
    queryKey: ['vouch-link-info', token],
    queryFn: () => lookupVouchLink(token),
    enabled: admitted,
    retry: false,
  })
  const vouch = useMutation({ mutationFn: () => vouchThroughLink(token) })

  if (!admitted) {
    return (
      <Card>
        <Alert kind="info">
          {person.status === 'revoked' ? t('revoked.text') : t('vouch.page.notAdmitted')}
        </Alert>
      </Card>
    )
  }
  if (info.isPending) {
    return (
      <Card>
        <p role="status" className="muted">
          {t('vouch.page.checking')}
        </p>
      </Card>
    )
  }
  if (info.isError) {
    return (
      <Card>
        <Alert kind="error">{vouchProblem(info.error, '')}</Alert>
      </Card>
    )
  }
  const data = info.data
  if (vouch.isSuccess) {
    return (
      <Card>
        <Alert kind="success">{t('vouch.page.done', { name: data.applicant_name })}</Alert>
      </Card>
    )
  }
  if (data.already_vouched) {
    return (
      <Card>
        <Alert kind="info">{t('vouch.page.already', { name: data.applicant_name })}</Alert>
      </Card>
    )
  }
  return (
    <Card>
      <p>
        {t('vouch.page.text', {
          name: data.applicant_name,
          church: data.church_name,
          group: data.home_group_name,
          goal: t(`vouch.page.goal.${data.requested_status}`),
        })}
      </p>
      <p className="hint">{t('vouch.page.warning')}</p>
      {vouch.isError && (
        <Alert kind="error" focus>
          {vouchProblem(vouch.error, data.applicant_name)}
        </Alert>
      )}
      <button
        type="button"
        className="btn btn-primary"
        disabled={vouch.isPending}
        onClick={() => vouch.mutate()}
      >
        {vouch.isPending
          ? t('vouch.page.working')
          : t('vouch.page.submit', { name: data.applicant_name })}
      </button>
    </Card>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="container">
      <div className="card">
        <h1>{t('vouch.page.title')}</h1>
        {children}
        <p>
          <Link to={PERSON_HOME}>{t('vouch.page.home')}</Link>
        </p>
      </div>
    </div>
  )
}
