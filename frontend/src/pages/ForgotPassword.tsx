import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { forgotPasswordRequest } from '../api/auth'
import { t } from '../i18n'
import { PERSON_SIGN_IN } from '../portals/config'
import { errorMessage } from '../shared/errors'
import { Alert, TextField } from '../shared/ui'
import { usePageTitle } from '../shared/usePageTitle'
import { forgotPasswordSchema, validate, type FieldErrors } from '../shared/validation'

export default function ForgotPassword() {
  usePageTitle(t('forgot.title'))
  const [values, setValues] = useState({ email: '', user_type: 'person' })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(forgotPasswordSchema, values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      await forgotPasswordRequest(result.data)
      setSent(true)
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('forgot.title')}</h1>
        {sent ? (
          <Alert kind="success">{t('forgot.done')}</Alert>
        ) : (
          <>
            <p>{t('forgot.text')}</p>
            <form onSubmit={onSubmit} noValidate className="form-grid">
              {formError && (
                <Alert kind="error" focus>
                  {formError}
                </Alert>
              )}
              <TextField
                label={t('field.email')}
                name="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                value={values.email}
                onChange={(value) => setValues((current) => ({ ...current, email: value }))}
                error={errors.email}
              />
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? t('forgot.working') : t('forgot.submit')}
              </button>
            </form>
          </>
        )}
        <p>
          <Link to={PERSON_SIGN_IN}>{t('forgot.back')}</Link>
        </p>
      </div>
    </div>
  )
}
