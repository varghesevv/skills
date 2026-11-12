import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { closeAccount, fetchChurches, fetchHomeGroups, updateApplication } from '../../api/person'
import type { AppliedStatus } from '../../api/types'
import { useAuth, usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, PasswordField, SelectField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

const APPLIED: readonly AppliedStatus[] = ['searcher', 'provider']
const KEEP = ''

/** A person waiting to be admitted: where they applied, the vouches so far, change or leave. */
export default function ApplicantHome() {
  usePageTitle(t('applicant.title'))
  const person = usePerson()
  const { setPerson } = useAuth()
  const [saved, setSaved] = useState(false)
  const appliedFor = person.requested_status ?? 'searcher'

  return (
    <div className="container">
      <div className="card">
        <h1>{t('applicant.title')}</h1>
        <p className="lead">{t('applicant.lead')}</p>
        <dl className="facts">
          <dt>{t('applicant.church')}</dt>
          <dd>{person.church.name}</dd>
          <dt>{t('applicant.group')}</dt>
          <dd>{person.home_group?.name}</dd>
          <dt>{t('applicant.leader')}</dt>
          <dd>{person.leader?.name}</dd>
          <dt>{t('applicant.applyingFor')}</dt>
          <dd>{t(`applicant.applyingFor.${appliedFor}`)}</dd>
          <dt>{t('applicant.vouches')}</dt>
          <dd>
            {person.vouch_count === 1
              ? t('applicant.vouchCount.one')
              : t('applicant.vouchCount', { count: person.vouch_count })}
          </dd>
        </dl>
        <p className="hint">{t('applicant.vouchesHelp')}</p>
      </div>
      <ChangeChoice
        key={`${person.home_group?.id}-${person.requested_status}`}
        saved={saved}
        onStart={() => setSaved(false)}
        onSaved={(updated) => {
          setPerson(updated)
          setSaved(true)
        }}
      />
      <Leave />
    </div>
  )
}

function ChangeChoice({
  saved,
  onStart,
  onSaved,
}: {
  saved: boolean
  onStart: () => void
  onSaved: (person: ReturnType<typeof usePerson>) => void
}) {
  const person = usePerson()
  const [churchId, setChurchId] = useState(person.church.id)
  const [groupId, setGroupId] = useState(KEEP)
  const [applied, setApplied] = useState<AppliedStatus>(person.requested_status ?? 'searcher')
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const churches = useQuery({ queryKey: ['churches'], queryFn: fetchChurches })
  const groups = useQuery({
    queryKey: ['home-groups', churchId],
    queryFn: () => fetchHomeGroups(churchId),
  })

  const unchanged = groupId === KEEP && applied === person.requested_status

  async function save(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    onStart()
    setBusy(true)
    try {
      const updated = await updateApplication({
        ...(groupId !== KEEP ? { home_group_id: groupId } : {}),
        requested_status: applied,
      })
      onSaved(updated)
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>{t('applicant.change.title')}</h2>
      <form onSubmit={save} noValidate className="form-grid">
        {formError && (
          <Alert kind="error" focus>
            {formError}
          </Alert>
        )}
        {saved && <Alert kind="success">{t('applicant.change.saved')}</Alert>}
        <SelectField
          className="span-2"
          label={t('applicant.change.church')}
          name="church"
          value={churchId}
          onChange={(value) => {
            setChurchId(value)
            setGroupId(KEEP)
          }}
          options={(churches.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }))}
        />
        <SelectField
          className="span-2"
          label={t('applicant.group')}
          name="group"
          value={groupId}
          onChange={setGroupId}
          options={[
            ...(churchId === person.church.id
              ? [{ value: KEEP, label: t('applicant.change.keep') }]
              : [{ value: KEEP, label: t('signup.group.choose') }]),
            ...(groups.data?.items ?? [])
              .filter((g) => g.id !== person.home_group?.id)
              .map((g) => ({
                value: g.id,
                label: `${g.name} (${t('signup.group.leader', { name: g.leader_name })})`,
              })),
          ]}
        />
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
        </fieldset>
        <button
          type="submit"
          className="btn btn-primary span-2"
          disabled={busy || unchanged || (churchId !== person.church.id && groupId === KEEP)}
        >
          {t('applicant.change.save')}
        </button>
      </form>
    </section>
  )
}

function Leave() {
  const { signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function leave(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    if (!password) return setFormError(t('validation.required'))
    setBusy(true)
    try {
      await closeAccount(password)
      await signOut() // every session of the closed account is already ended
      navigate('/', { replace: true })
    } catch (error) {
      setFormError(errorMessage(error))
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>{t('applicant.leave.title')}</h2>
      <p>{t('applicant.leave.text')}</p>
      {!open ? (
        <button type="button" className="btn btn-quiet" onClick={() => setOpen(true)}>
          {t('applicant.leave.open')}
        </button>
      ) : (
        <form onSubmit={leave} noValidate className="form-grid">
          {formError && (
            <Alert kind="error" focus>
              {formError}
            </Alert>
          )}
          <PasswordField
            className="span-2"
            label={t('applicant.leave.confirm')}
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
          />
          <button type="submit" className="btn btn-danger span-2" disabled={busy}>
            {busy ? t('applicant.leave.working') : t('applicant.leave.submit')}
          </button>
        </form>
      )}
    </section>
  )
}
