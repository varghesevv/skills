import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import type { UserType } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { t } from '../i18n'
import { landingTarget } from '../portals/config'
import { errorMessage } from '../shared/errors'
import { Alert, PasswordField, SelectField, TextField } from '../shared/ui'
import { usePageTitle } from '../shared/usePageTitle'
import { loginSchema, validate, type FieldErrors } from '../shared/validation'

export const USER_TYPE_OPTIONS = [
  { value: 'freelancer', label: t('role.freelancer') },
  { value: 'workhost', label: t('role.workhost') },
  { value: 'organisation', label: t('role.organisation') },
  { value: 'admin', label: t('role.admin') },
] as const

export function isUserType(value: string | null): value is UserType {
  return USER_TYPE_OPTIONS.some((option) => option.value === value)
}

export default function Login() {
  usePageTitle(t('login.title'))
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const from = (location.state as { from?: unknown } | null)?.from
  const typeParam = params.get('type')

  const [values, setValues] = useState({
    email: '',
    password: '',
    user_type: isUserType(typeParam) ? typeParam : 'freelancer',
  })
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
    const result = validate(loginSchema, values)
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
    <div className="container">
      <div className="card auth-card">
        <h1>{t('login.title')}</h1>
        <form onSubmit={onSubmit} noValidate className="form-grid">
          {formError && (
            <Alert kind="error" focus>
              {formError}
            </Alert>
          )}
          <SelectField
            className="span-2"
            label={t('field.userType')}
            name="user_type"
            value={values.user_type}
            onChange={(value) => set('user_type', value)}
            options={USER_TYPE_OPTIONS}
            error={errors.user_type}
          />
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
          <Link to="/forgot-password">{t('login.forgot')}</Link>
        </p>
        <p>
          {t('login.noAccount')} <Link to="/register">{t('nav.register')}</Link>
        </p>
      </div>
    </div>
  )
}
