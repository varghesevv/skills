import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { resetPasswordRequest } from '../api/auth'
import { t } from '../i18n'
import { errorMessage, serverFieldErrors } from '../shared/errors'
import { Alert, PasswordField } from '../shared/ui'
import { usePageTitle } from '../shared/usePageTitle'
import { resetPasswordSchema, validate, type FieldErrors } from '../shared/validation'

export default function ResetPassword() {
  usePageTitle(t('reset.title'))
  const [params] = useSearchParams()
  const token = params.get('token')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(resetPasswordSchema, { new_password: password })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      await resetPasswordRequest({ token: token ?? '', new_password: result.data.new_password })
      setDone(true)
    } catch (error) {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('reset.title')}</h1>
        {done ? (
          <>
            <Alert kind="success">{t('reset.done')}</Alert>
            <Link className="btn btn-primary" to="/login">
              {t('nav.logIn')}
            </Link>
          </>
        ) : !token ? (
          <>
            <Alert kind="error">{t('reset.missingToken')}</Alert>
            <Link className="btn btn-primary" to="/forgot-password">
              {t('reset.requestNew')}
            </Link>
          </>
        ) : (
          <form onSubmit={onSubmit} noValidate className="form-grid">
            {formError && (
              <Alert kind="error" focus>
                {formError}
              </Alert>
            )}
            <PasswordField
              label={t('field.newPassword')}
              name="new_password"
              autoComplete="new-password"
              hint={t('field.passwordHint')}
              value={password}
              onChange={setPassword}
              error={errors.new_password}
            />
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? t('reset.working') : t('reset.submit')}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
