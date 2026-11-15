import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { closeAccount } from '../../api/person'
import { ApiError } from '../../api/http'
import { useAuth } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, PasswordField } from '../../shared/ui'

/** What the server's refusals of closing an account mean, in words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'leads_a_group') return t('applicant.leave.error.leadsGroup')
    if (error.code === 'leads_a_church') return t('applicant.leave.error.leadsChurch')
    if (error.code === 'account_revoked') return t('applicant.leave.error.revoked')
  }
  return errorMessage(error)
}

/** Close one's own account, after asking for the password again. A leader hands their group on
 *  first, an ADMIN or the OWNER their role; the server decides and says so. */
export default function LeaveAccount() {
  const { signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const confirmation = useRef<HTMLDivElement>(null)

  // The confirmation replaces the button: move focus to it, and give it back on cancel.
  useEffect(() => {
    if (open) confirmation.current?.focus()
  }, [open])

  function cancel() {
    setOpen(false)
    setPassword('')
    setFormError(null)
    window.setTimeout(() => trigger.current?.focus(), 0)
  }

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
      setFormError(problem(error))
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>{t('applicant.leave.title')}</h2>
      <p>{t('applicant.leave.text')}</p>
      {!open ? (
        <button ref={trigger} type="button" className="btn btn-quiet" onClick={() => setOpen(true)}>
          {t('applicant.leave.open')}
        </button>
      ) : (
        <form onSubmit={leave} noValidate className="form-grid">
          <div
            ref={confirmation}
            tabIndex={-1}
            className="span-2"
            role="group"
            aria-label={t('applicant.leave.title')}
          >
            <p>{t('applicant.leave.warning')}</p>
          </div>
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
          <div className="form-actions span-2">
            <button type="button" className="btn btn-quiet" onClick={cancel} disabled={busy}>
              {t('applicant.leave.cancel')}
            </button>
            <button type="submit" className="btn btn-danger" disabled={busy}>
              {busy ? t('applicant.leave.working') : t('applicant.leave.submit')}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
