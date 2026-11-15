import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { updateMe } from '../../api/person'
import { useAuth, usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { accountDetailsSchema, validate, type FieldErrors } from '../../shared/validation'
import LeaveAccount from './LeaveAccount'

/** The account and settings of a person: their details, and closing the account. */
export default function Account() {
  usePageTitle(t('account.title'))
  const person = usePerson()
  const { setPerson } = useAuth()
  const [name, setName] = useState(person.full_name)
  const [mobile, setMobile] = useState(person.mobile_number)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = useMutation({
    mutationFn: updateMe,
    onSuccess: (updated) => {
      setPerson(updated)
      setName(updated.full_name)
      setMobile(updated.mobile_number)
      setSaved(true)
    },
    onError: (error) => {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    setSaved(false)
    const result = validate(accountDetailsSchema, { full_name: name, mobile_number: mobile })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    save.mutate(result.data)
  }

  return (
    <div className="container">
      <h1>{t('account.title')}</h1>
      <p className="lead">{t('account.lead')}</p>
      <form onSubmit={onSubmit} noValidate className="card form-grid">
        <h2>{t('account.details')}</h2>
        {formError && (
          <Alert kind="error" focus>
            {formError}
          </Alert>
        )}
        {saved && <Alert kind="success">{t('account.saved')}</Alert>}
        <TextField
          label={t('field.fullName')}
          name="full_name"
          autoComplete="name"
          value={name}
          onChange={(value) => {
            setSaved(false)
            setName(value)
          }}
          error={errors.full_name}
        />
        <TextField
          label={t('field.mobile')}
          name="mobile_number"
          type="tel"
          autoComplete="tel"
          inputMode="tel"
          hint={t('field.mobileHint')}
          value={mobile}
          onChange={(value) => {
            setSaved(false)
            setMobile(value)
          }}
          error={errors.mobile_number}
        />
        <div className="field">
          <span className="field-label">{t('account.email')}</span>
          <p>{person.email}</p>
          <p className="field-hint">{t('account.emailHint')}</p>
        </div>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {save.isPending ? t('account.saving') : t('account.save')}
        </button>
      </form>
      <LeaveAccount />
    </div>
  )
}
