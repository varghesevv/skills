import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { acceptAdminInvitation, lookupAdminInvitation } from '../../api/person'
import type { AdminInvitationInfo } from '../../api/types'
import { ApiError } from '../../api/http'
import { t } from '../../i18n'
import { PERSON_SIGN_IN } from '../../portals/config'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, LoadingScreen, PasswordField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { acceptInvitationSchema, validate, type FieldErrors } from '../../shared/validation'

type Lookup =
  | { state: 'checking' }
  | { state: 'ok'; info: AdminInvitationInfo }
  | { state: 'bad' }
  | { state: 'failed'; error: unknown }

/** What a refused acceptance means. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'church_name_taken') return t('invite.error.churchTaken')
    if (error.code === 'group_name_taken') return t('invite.error.taken')
    if (error.code === 'account_exists') return t('invite.error.account')
    if (error.code === 'not_found') return t('invite.bad')
  }
  return errorMessage(error)
}

/** The page an invited ADMIN opens (`/invite/<token>`): the church and the domain of the address,
 *  then a form for the person's details and the name of their first home group. */
export default function AcceptInvitation() {
  usePageTitle(t('invite.title'))
  const { token = '' } = useParams()
  const [lookup, setLookup] = useState<Lookup>({ state: 'checking' })
  const [values, setValues] = useState({
    full_name: '',
    mobile_number: '',
    password: '',
    home_group_name: '',
  })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLookup({ state: 'checking' })
    lookupAdminInvitation(token).then(
      (info) => !cancelled && setLookup({ state: 'ok', info }),
      // Only the server's own "no such invitation" says the link is dead; an outage must not.
      (error: unknown) =>
        !cancelled &&
        setLookup(
          error instanceof ApiError && error.code === 'not_found'
            ? { state: 'bad' }
            : { state: 'failed', error },
        ),
    )
    return () => {
      cancelled = true
    }
  }, [token, attempt])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const result = validate(acceptInvitationSchema, values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    setFormError(null)
    try {
      await acceptAdminInvitation({ token, ...result.data })
      setDone(true)
    } catch (error) {
      const fields = serverFieldErrors(error)
      if (Object.keys(fields).length > 0) setErrors(fields)
      if (error instanceof ApiError && error.code === 'not_found') setLookup({ state: 'bad' })
      setFormError(problem(error))
    } finally {
      setBusy(false)
    }
  }

  const set = (field: keyof typeof values) => (value: string) =>
    setValues((current) => ({ ...current, [field]: value }))

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{done ? t('invite.done.title') : t('invite.title')}</h1>
        {lookup.state === 'checking' && <LoadingScreen />}
        {lookup.state === 'bad' && !done && <Alert kind="error">{t('invite.bad')}</Alert>}
        {lookup.state === 'failed' && !done && (
          <Alert kind="error">
            <p>{errorMessage(lookup.error)}</p>
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => setAttempt((n) => n + 1)}
            >
              {t('common.retry')}
            </button>
          </Alert>
        )}
        {done && (
          <>
            <Alert kind="success">{t('invite.done.text')}</Alert>
            <p>
              <Link className="btn btn-primary" to={PERSON_SIGN_IN}>
                {t('member.signIn.title')}
              </Link>
            </p>
          </>
        )}
        {lookup.state === 'ok' && !done && (
          <form onSubmit={submit} noValidate className="form-grid">
            <p className="lead span-2">
              {t('invite.lead', {
                church: lookup.info.church_name,
                domain: lookup.info.email_domain,
              })}
            </p>
            {formError && (
              <Alert kind="error" focus>
                {formError}
              </Alert>
            )}
            <TextField
              className="span-2"
              label={t('field.fullName')}
              name="full_name"
              autoComplete="name"
              value={values.full_name}
              onChange={set('full_name')}
              error={errors.full_name}
            />
            <TextField
              className="span-2"
              label={t('field.mobile')}
              name="mobile_number"
              type="tel"
              autoComplete="tel"
              inputMode="tel"
              hint={t('field.mobileHint')}
              value={values.mobile_number}
              onChange={set('mobile_number')}
              error={errors.mobile_number}
            />
            <PasswordField
              className="span-2"
              label={t('field.newPassword')}
              name="password"
              autoComplete="new-password"
              hint={t('field.passwordHint')}
              value={values.password}
              onChange={set('password')}
              error={errors.password}
            />
            <TextField
              className="span-2"
              label={t('invite.group')}
              name="home_group_name"
              hint={t('invite.groupHint')}
              value={values.home_group_name}
              onChange={set('home_group_name')}
              error={errors.home_group_name}
            />
            <div className="form-actions span-2">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? t('invite.working') : t('invite.submit')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
