import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { ZodTypeAny } from 'zod'

import { registerRequest } from '../api/auth'
import { ApiError } from '../api/http'
import type { RegisterResponse, RegisterType } from '../api/types'
import { t, type StringKey } from '../i18n'
import { errorMessage, serverFieldErrors } from '../shared/errors'
import { Alert, CheckboxField, PasswordField, TextField } from '../shared/ui'
import { usePageTitle } from '../shared/usePageTitle'
import {
  freelancerRegisterSchema,
  organisationRegisterSchema,
  validate,
  workhostRegisterSchema,
  type FieldErrors,
} from '../shared/validation'
import NotFound from './NotFound'

const REGISTER_TYPES: readonly RegisterType[] = ['freelancer', 'workhost', 'organisation']

const SCHEMAS: Record<RegisterType, ZodTypeAny> = {
  freelancer: freelancerRegisterSchema,
  workhost: workhostRegisterSchema,
  organisation: organisationRegisterSchema,
}

const TITLES: Record<RegisterType, StringKey> = {
  freelancer: 'register.freelancer.title',
  workhost: 'register.workhost.title',
  organisation: 'register.organisation.title',
}

export function RegisterChoice() {
  usePageTitle(t('register.title'))
  return (
    <div className="container">
      <h1>{t('register.title')}</h1>
      <p className="lead">{t('register.choose')}</p>
      <ul className="choice-grid">
        {REGISTER_TYPES.map((type) => (
          <li key={type} className="card">
            <h2>{t(`landing.${type}.title`)}</h2>
            <p>{t(`landing.${type}.text`)}</p>
            <Link className="btn btn-primary" to={`/register/${type}`}>
              {t(`role.${type}`)}
            </Link>
          </li>
        ))}
      </ul>
      <p>
        {t('register.haveAccount')} <Link to="/login">{t('nav.logIn')}</Link>
      </p>
    </div>
  )
}

type Values = {
  email: string
  mobile_number: string
  password: string
  org_name: string
  nationality: string
  primary_language: string
  whatsapp_availability: boolean
}

const EMPTY: Values = {
  email: '',
  mobile_number: '',
  password: '',
  org_name: '',
  nationality: '',
  primary_language: '',
  whatsapp_availability: false,
}

function pick(type: RegisterType, data: Record<string, unknown>): Record<string, unknown> {
  // Optional text left empty is sent as null so the API stores nothing.
  const body: Record<string, unknown> = { ...data }
  for (const key of ['nationality', 'primary_language']) {
    if (body[key] === '') body[key] = null
  }
  if (type !== 'freelancer') {
    delete body.nationality
    delete body.primary_language
    delete body.whatsapp_availability
  }
  return body
}

function RegisterForm({ type }: { type: RegisterType }) {
  usePageTitle(t(TITLES[type]))
  const [values, setValues] = useState<Values>(EMPTY)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<RegisterResponse | null>(null)

  function set<K extends keyof Values>(name: K, value: Values[K]) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const result = validate(SCHEMAS[type], values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setBusy(true)
    try {
      setCreated(await registerRequest(type, pick(type, result.data as Record<string, unknown>)))
    } catch (error) {
      const fieldErrors = serverFieldErrors(error)
      if (error instanceof ApiError && error.code === 'email_taken') {
        fieldErrors.email = t('error.emailTaken')
      }
      setErrors(fieldErrors)
      setFormError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  if (created) {
    return (
      <div className="container">
        <div className="card auth-card">
          <h1>{t('register.done.title')}</h1>
          <Alert kind="success">
            {created.approval_status === 'pending'
              ? t('register.done.pending')
              : t('register.done.text')}
          </Alert>
          <Link className="btn btn-primary" to={`/login?type=${type}`}>
            {t('register.done.login')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <div className="card form-card">
        <h1>{t(TITLES[type])}</h1>
        <form onSubmit={onSubmit} noValidate className="form-grid cols-2">
          {formError && (
            <div className="span-2">
              <Alert kind="error" focus>
                {formError}
              </Alert>
            </div>
          )}
          {type === 'organisation' && (
            <TextField
              className="span-2"
              label={t('field.orgName')}
              name="org_name"
              autoComplete="organization"
              value={values.org_name}
              onChange={(value) => set('org_name', value)}
              error={errors.org_name}
            />
          )}
          <TextField
            label={t('field.email')}
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            value={values.email}
            onChange={(value) => set('email', value)}
            error={errors.email}
          />
          <TextField
            label={t('field.mobile')}
            name="mobile_number"
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            hint={t('field.mobileHint')}
            value={values.mobile_number}
            onChange={(value) => set('mobile_number', value)}
            error={errors.mobile_number}
          />
          <PasswordField
            className="span-2"
            label={t('field.password')}
            name="password"
            autoComplete="new-password"
            hint={t('field.passwordHint')}
            value={values.password}
            onChange={(value) => set('password', value)}
            error={errors.password}
          />
          {type === 'freelancer' && (
            <>
              <TextField
                label={t('field.nationality')}
                name="nationality"
                value={values.nationality}
                onChange={(value) => set('nationality', value)}
                error={errors.nationality}
              />
              <TextField
                label={t('field.language')}
                name="primary_language"
                value={values.primary_language}
                onChange={(value) => set('primary_language', value)}
                error={errors.primary_language}
              />
              <CheckboxField
                className="span-2"
                label={t('field.whatsapp')}
                name="whatsapp_availability"
                checked={values.whatsapp_availability}
                onChange={(checked) => set('whatsapp_availability', checked)}
              />
            </>
          )}
          <button type="submit" className="btn btn-primary span-2" disabled={busy}>
            {busy ? t('register.working') : t('register.submit')}
          </button>
        </form>
        <p>
          {t('register.haveAccount')} <Link to={`/login?type=${type}`}>{t('nav.logIn')}</Link>
        </p>
      </div>
    </div>
  )
}

export default function Register() {
  const { type } = useParams()
  if (!REGISTER_TYPES.includes(type as RegisterType)) return <NotFound />
  return <RegisterForm key={type} type={type as RegisterType} />
}
