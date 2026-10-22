import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import type { UserType } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { landingTarget } from '../../portals/config'
import { errorMessage } from '../../shared/errors'
import { Alert, PasswordField, TextField } from '../../shared/ui'
import { loginSchema, validate, type FieldErrors } from '../../shared/validation'

/**
 * Email and password for one kind of account. The account type is fixed by the page, so a
 * person on the organisation page can only log in as an organisation, and so on.
 */
export default function LoginForm({ userType }: { userType: UserType }) {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: unknown } | null)?.from

  const [values, setValues] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={landingTarget(user.user_type, from)} replace />

  function set(name: keyof typeof values, value: string) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(loginSchema, { ...values, user_type: userType })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      const me = await signIn(result.data)
      navigate(landingTarget(me.user_type, from), { replace: true })
    } catch (error) {
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
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
          onChange={(value) => set('email', value)}
          error={errors.email}
        />
        <PasswordField
          className="span-2"
          label={t('field.password')}
          name="password"
          autoComplete="current-password"
          value={values.password}
          onChange={(value) => set('password', value)}
          error={errors.password}
        />
        <button type="submit" className="btn btn-primary span-2" disabled={busy}>
          {busy ? t('login.working') : t('login.submit')}
        </button>
      </form>
      <p>
        <Link to={`/forgot-password?type=${userType}`}>{t('login.forgot')}</Link>
      </p>
    </>
  )
}
