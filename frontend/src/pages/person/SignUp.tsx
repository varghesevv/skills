import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchChurches, fetchHomeGroups, lookupInvitation, signupRequest } from '../../api/person'
import type { AppliedStatus, InvitationInfo } from '../../api/types'
import { t } from '../../i18n'
import { PERSON_SIGN_IN, PERSON_SIGN_UP } from '../../portals/config'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, LoadingScreen, PasswordField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { signupDetailsSchema, validate, type FieldErrors } from '../../shared/validation'

type Step = 'details' | 'church' | 'group' | 'status'

const APPLIED: readonly AppliedStatus[] = ['searcher', 'provider']

type Invitation =
  | { state: 'none' }
  | { state: 'checking' }
  | { state: 'ok'; info: InvitationInfo }
  | { state: 'bad' }

/**
 * Joining: about you, then the church and the home group (a group invitation link skips both),
 * then whether to find providers or offer skills. The new person is pending until the leader of
 * the chosen home group admits them.
 */
export default function SignUp() {
  usePageTitle(t('member.signUp.title'))
  const { token } = useParams()
  const [invitation, setInvitation] = useState<Invitation>(
    token ? { state: 'checking' } : { state: 'none' },
  )
  const [step, setStep] = useState<Step>('details')
  const [details, setDetails] = useState({
    full_name: '',
    email: '',
    mobile_number: '',
    password: '',
  })
  const [churchId, setChurchId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [applied, setApplied] = useState<AppliedStatus>('searcher')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    lookupInvitation(token).then(
      (info) => !cancelled && setInvitation({ state: 'ok', info }),
      () => !cancelled && setInvitation({ state: 'bad' }),
    )
    return () => {
      cancelled = true
    }
  }, [token])

  const invited = invitation.state === 'ok'
  const steps: Step[] = invited ? ['details', 'status'] : ['details', 'church', 'group', 'status']
  const index = steps.indexOf(step)

  const churches = useQuery({
    queryKey: ['churches'],
    queryFn: fetchChurches,
    enabled: step === 'church',
  })
  const groups = useQuery({
    queryKey: ['home-groups', churchId],
    queryFn: () => fetchHomeGroups(churchId),
    enabled: step === 'group' && churchId !== '',
  })

  if (invitation.state === 'checking') {
    return (
      <div className="container">
        <LoadingScreen />
      </div>
    )
  }
  if (done) {
    return (
      <div className="container">
        <div className="card auth-card">
          <h1>{t('signup.done.title')}</h1>
          <Alert kind="success">{t('signup.done.text')}</Alert>
          <p>
            <Link className="btn btn-primary" to={PERSON_SIGN_IN}>
              {t('member.signIn.title')}
            </Link>
          </p>
        </div>
      </div>
    )
  }

  function go(offset: number) {
    setFormError(null)
    setStep(steps[Math.min(Math.max(index + offset, 0), steps.length - 1)])
  }

  function next() {
    setFormError(null)
    if (step === 'details') {
      const result = validate(signupDetailsSchema, details)
      if (!result.ok) {
        setErrors(result.errors)
        return
      }
      setErrors({})
    }
    if (step === 'church' && !churchId) return setFormError(t('signup.church.choose'))
    if (step === 'group' && !groupId) return setFormError(t('signup.group.choose'))
    go(1)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (step !== 'status') return next()
    const result = validate(signupDetailsSchema, details)
    if (!result.ok) {
      setErrors(result.errors)
      setStep('details')
      return
    }
    setBusy(true)
    setFormError(null)
    try {
      await signupRequest({
        ...result.data,
        requested_status: applied,
        ...(token && invited ? { invitation_token: token } : { home_group_id: groupId }),
      })
      setDone(true)
    } catch (error) {
      const fields = serverFieldErrors(error)
      if (Object.keys(fields).length > 0) {
        setErrors(fields)
        setStep('details')
      }
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  const stepName = t(`signup.step.${step}`)
  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('member.signUp.title')}</h1>
        <p className="lead">{t('member.signUp.lead')}</p>
        {invitation.state === 'ok' && (
          <Alert kind="info">
            {t('signup.invited', {
              group: invitation.info.home_group_name,
              church: invitation.info.church_name,
              leader: invitation.info.leader_name,
            })}
          </Alert>
        )}
        {invitation.state === 'bad' && (
          <Alert kind="error">
            {t('signup.invitationBad')}{' '}
            <Link to={PERSON_SIGN_UP}>{t('signup.chooseYourself')}</Link>
          </Alert>
        )}
        <p className="step-label" aria-live="polite">
          {t('signup.step', { number: index + 1, total: steps.length, name: stepName })}
        </p>
        <form onSubmit={submit} noValidate className="form-grid">
          {formError && (
            <Alert kind="error" focus>
              {formError}
            </Alert>
          )}
          {step === 'details' && (
            <>
              <TextField
                className="span-2"
                label={t('field.fullName')}
                name="full_name"
                autoComplete="name"
                value={details.full_name}
                onChange={(value) => setDetails((current) => ({ ...current, full_name: value }))}
                error={errors.full_name}
              />
              <TextField
                className="span-2"
                label={t('field.email')}
                name="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                value={details.email}
                onChange={(value) => setDetails((current) => ({ ...current, email: value }))}
                error={errors.email}
              />
              <TextField
                className="span-2"
                label={t('field.mobile')}
                name="mobile_number"
                type="tel"
                autoComplete="tel"
                inputMode="tel"
                hint={t('field.mobileHint')}
                value={details.mobile_number}
                onChange={(value) =>
                  setDetails((current) => ({ ...current, mobile_number: value }))
                }
                error={errors.mobile_number}
              />
              <PasswordField
                className="span-2"
                label={t('field.newPassword')}
                name="password"
                autoComplete="new-password"
                hint={t('field.passwordHint')}
                value={details.password}
                onChange={(value) => setDetails((current) => ({ ...current, password: value }))}
                error={errors.password}
              />
            </>
          )}
          {step === 'church' && (
            <fieldset className="span-2 choice-list">
              <legend>{t('signup.church.choose')}</legend>
              {churches.isPending && <LoadingScreen />}
              {churches.data?.items.length === 0 && <p>{t('signup.none.church')}</p>}
              {churches.isError && <Alert kind="error">{errorMessage(churches.error)}</Alert>}
              {churches.data?.items.map((church) => (
                <label key={church.id} className="choice">
                  <input
                    type="radio"
                    name="church"
                    value={church.id}
                    checked={churchId === church.id}
                    onChange={() => {
                      setChurchId(church.id)
                      setGroupId('')
                    }}
                  />
                  {church.name}
                </label>
              ))}
            </fieldset>
          )}
          {step === 'group' && (
            <fieldset className="span-2 choice-list">
              <legend>{t('signup.group.choose')}</legend>
              {groups.isPending && <LoadingScreen />}
              {groups.data?.items.length === 0 && <p>{t('signup.none.group')}</p>}
              {groups.isError && <Alert kind="error">{errorMessage(groups.error)}</Alert>}
              {groups.data?.items.map((group) => (
                <label key={group.id} className="choice">
                  <input
                    type="radio"
                    name="group"
                    value={group.id}
                    checked={groupId === group.id}
                    onChange={() => setGroupId(group.id)}
                  />
                  <span>
                    {group.name}
                    <small> {t('signup.group.leader', { name: group.leader_name })}</small>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          {step === 'status' && (
            <fieldset className="span-2 choice-list">
              <legend>{t('signup.apply.title')}</legend>
              {APPLIED.map((status) => (
                <label key={status} className="choice">
                  <input
                    type="radio"
                    name="applied"
                    value={status}
                    checked={applied === status}
                    onChange={() => setApplied(status)}
                  />
                  {t(`signup.apply.${status}`)}
                </label>
              ))}
              <p className="hint">{t('signup.apply.hint')}</p>
            </fieldset>
          )}
          <div className="form-actions span-2">
            {index > 0 && (
              <button type="button" className="btn btn-quiet" onClick={() => go(-1)}>
                {t('signup.back')}
              </button>
            )}
            {step === 'status' ? (
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? t('signup.working') : t('signup.submit')}
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={next}>
                {t('signup.next')}
              </button>
            )}
          </div>
        </form>
        <p>
          {t('member.signUp.haveAccount')}{' '}
          <Link to={PERSON_SIGN_IN}>{t('member.signIn.title')}</Link>
        </p>
      </div>
    </div>
  )
}
