import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { getProfile, updateProfile } from '../../api/freelancer'
import type { FreelancerProfile } from '../../api/types'
import { t } from '../../i18n'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, CheckboxField, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { freelancerProfileSchema, validate, type FieldErrors } from '../../shared/validation'

export const PROFILE_KEY = ['freelancer', 'profile'] as const

const CURRENCIES = ['AED', 'USD', 'EUR', 'GBP', 'INR', 'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'PHP']

type Values = {
  full_name: string
  mobile_number: string
  whatsapp_availability: boolean
  nationality: string
  primary_language: string
  rate_per_hour: string
  rate_currency: string
  is_rate_negotiable: boolean
}

function initialValues(profile: FreelancerProfile): Values {
  return {
    full_name: profile.full_name ?? '',
    mobile_number: profile.mobile_number,
    whatsapp_availability: profile.whatsapp_availability,
    nationality: profile.nationality ?? '',
    primary_language: profile.primary_language ?? '',
    rate_per_hour: profile.rate_per_hour === null ? '' : String(profile.rate_per_hour),
    rate_currency: profile.rate_currency ?? '',
    is_rate_negotiable: profile.is_rate_negotiable,
  }
}

function ProfileForm({ profile }: { profile: FreelancerProfile }) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState(() => initialValues(profile))
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: updateProfile,
    onSuccess: (updated) => {
      queryClient.setQueryData(PROFILE_KEY, updated)
      setValues(initialValues(updated))
      setSaved(true)
    },
    onError: (error) => {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
    },
  })

  function set<K extends keyof Values>(name: K, value: Values[K]) {
    setSaved(false)
    setValues((current) => ({ ...current, [name]: value }))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    setSaved(false)
    const result = validate(freelancerProfileSchema, values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    const data = result.data
    save.mutate({
      full_name: data.full_name,
      mobile_number: data.mobile_number,
      whatsapp_availability: data.whatsapp_availability,
      nationality: data.nationality || null,
      primary_language: data.primary_language || null,
      rate_per_hour: data.rate_per_hour === '' ? null : Number(data.rate_per_hour),
      rate_currency: data.rate_currency === '' ? null : data.rate_currency,
      is_rate_negotiable: data.is_rate_negotiable,
    })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-card form-grid cols-2">
      {formError && (
        <div className="span-2">
          <Alert kind="error" focus>
            {formError}
          </Alert>
        </div>
      )}
      {saved && (
        <div className="span-2">
          <Alert kind="success">{t('common.saved')}</Alert>
        </div>
      )}
      <h2 className="span-2">{t('profile.contact')}</h2>
      <TextField
        className="span-2"
        label={t('field.fullName')}
        name="full_name"
        autoComplete="name"
        value={values.full_name}
        onChange={(value) => set('full_name', value)}
        error={errors.full_name}
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
      <CheckboxField
        label={t('field.whatsapp')}
        name="whatsapp_availability"
        checked={values.whatsapp_availability}
        onChange={(checked) => set('whatsapp_availability', checked)}
      />
      <TextField
        label={t('profile.nationality')}
        name="nationality"
        value={values.nationality}
        onChange={(value) => set('nationality', value)}
        error={errors.nationality}
      />
      <TextField
        label={t('profile.language')}
        name="primary_language"
        value={values.primary_language}
        onChange={(value) => set('primary_language', value)}
        error={errors.primary_language}
      />

      <h2 className="span-2">{t('profile.rateSection')}</h2>
      <TextField
        label={t('profile.rate')}
        name="rate_per_hour"
        inputMode="decimal"
        value={values.rate_per_hour}
        onChange={(value) => set('rate_per_hour', value)}
        error={errors.rate_per_hour}
      />
      <TextField
        label={t('profile.currency')}
        name="rate_currency"
        autoComplete="off"
        maxLength={3}
        list="currency-codes"
        hint={t('profile.currencyHint')}
        value={values.rate_currency}
        onChange={(value) => set('rate_currency', value)}
        error={errors.rate_currency}
      />
      <datalist id="currency-codes">
        {CURRENCIES.map((code) => (
          <option key={code} value={code} />
        ))}
      </datalist>
      <CheckboxField
        className="span-2"
        label={t('profile.negotiable')}
        name="is_rate_negotiable"
        checked={values.is_rate_negotiable}
        onChange={(checked) => set('is_rate_negotiable', checked)}
      />

      <button type="submit" className="btn btn-primary span-2" disabled={save.isPending}>
        {save.isPending ? t('common.saving') : t('common.save')}
      </button>
    </form>
  )
}

export default function ProfilePage() {
  usePageTitle(t('profile.title'))
  const query = useQuery({ queryKey: PROFILE_KEY, queryFn: getProfile })
  return (
    <>
      <h1>{t('profile.title')}</h1>
      <p className="lead">{t('profile.lead')}</p>
      <QueryBoundary query={query}>
        {(profile) => <ProfileForm key={profile.id} profile={profile} />}
      </QueryBoundary>
    </>
  )
}
