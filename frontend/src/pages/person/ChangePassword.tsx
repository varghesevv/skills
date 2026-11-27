import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { changePasswordRequest, fetchMe } from '../../api/auth'
import { useAuth } from '../../auth/AuthContext'
import { setTokens } from '../../auth/tokenStore'
import { t } from '../../i18n'
import { PERSON_HOME } from '../../portals/config'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, PasswordField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { changePasswordSchema, validate, type FieldErrors } from '../../shared/validation'

/** A person created from the initial config signs in with a temporary password and is kept here
 * until they choose their own (story S100). */
export default function ChangePassword() {
  usePageTitle(t('changePassword.title'))
  const { setPerson, signOut } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState({ current_password: '', new_password: '' })
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(changePasswordSchema, values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      // Every other session ends; the answer holds the tokens of this one.
      const tokens = await changePasswordRequest(result.data)
      setTokens(tokens.access_token, tokens.refresh_token)
      const me = await fetchMe()
      if (me.user_type === 'person') setPerson(me)
      navigate(PERSON_HOME, { replace: true })
    } catch (error) {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="card auth-card">
        <h1>{t('changePassword.title')}</h1>
        <p>{t('changePassword.text')}</p>
        <form onSubmit={onSubmit} noValidate className="form-grid">
          {formError && (
            <Alert kind="error" focus>
              {formError}
            </Alert>
          )}
          <PasswordField
            label={t('changePassword.current')}
            name="current_password"
            autoComplete="current-password"
            value={values.current_password}
            onChange={(value) => setValues((v) => ({ ...v, current_password: value }))}
            error={errors.current_password}
          />
          <PasswordField
            label={t('field.newPassword')}
            name="new_password"
            autoComplete="new-password"
            hint={t('field.passwordHint')}
            value={values.new_password}
            onChange={(value) => setValues((v) => ({ ...v, new_password: value }))}
            error={errors.new_password}
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? t('changePassword.working') : t('changePassword.submit')}
          </button>
          <button type="button" className="btn" onClick={() => void signOut()} disabled={busy}>
            {t('nav.logOut')}
          </button>
        </form>
      </div>
    </div>
  )
}
