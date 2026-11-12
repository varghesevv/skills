import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { homePath, PERSON_HOME, PERSON_SIGN_UP } from '../../portals/config'
import { errorMessage } from '../../shared/errors'
import { Alert, PasswordField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { personLoginSchema, validate, type FieldErrors } from '../../shared/validation'

/** The one login for every person: email and password, no account type. */
export default function PersonSignIn() {
  usePageTitle(t('member.signIn.title'))
  const { user, signInPerson } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) {
    return (
      <Navigate to={user.user_type === 'person' ? PERSON_HOME : homePath(user.user_type)} replace />
    )
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(personLoginSchema, values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      await signInPerson(result.data)
      navigate(PERSON_HOME, { replace: true })
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('member.signIn.title')}</h1>
        <p>{t('member.signIn.text')}</p>
        <form onSubmit={onSubmit} noValidate className="form-grid">
          {formError && (
            <Alert kind="error" focus>
              {formError}
            </Alert>
          )}
          <TextField
            className="span-2"
            label={t('field.email')}
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            value={values.email}
            onChange={(value) => setValues((current) => ({ ...current, email: value }))}
            error={errors.email}
          />
          <PasswordField
            className="span-2"
            label={t('field.password')}
            name="password"
            autoComplete="current-password"
            value={values.password}
            onChange={(value) => setValues((current) => ({ ...current, password: value }))}
            error={errors.password}
          />
          <button type="submit" className="btn btn-primary span-2" disabled={busy}>
            {busy ? t('login.working') : t('login.submit')}
          </button>
        </form>
        <p>
          <Link to="/forgot-password?type=person">{t('login.forgot')}</Link>
        </p>
        <p>
          {t('member.signIn.noAccount')} <Link to={PERSON_SIGN_UP}>{t('member.signUp.title')}</Link>
        </p>
      </div>
    </div>
  )
}
