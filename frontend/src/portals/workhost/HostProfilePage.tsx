import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { getHostProfile, updateHostProfile } from '../../api/workhost'
import { DAYS, type Day, type WorkHostProfile } from '../../api/types'
import { t } from '../../i18n'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, CheckboxField, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { hostProfileSchema, validate, type FieldErrors } from '../../shared/validation'

const KEY = ['host', 'profile'] as const

function HostProfileForm({ profile }: { profile: WorkHostProfile }) {
  const queryClient = useQueryClient()
  const [fullName, setFullName] = useState(profile.full_name ?? '')
  const [mobile, setMobile] = useState(profile.mobile_number)
  const [days, setDays] = useState<Day[]>(profile.available_days)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: updateHostProfile,
    onSuccess: (updated) => {
      queryClient.setQueryData(KEY, updated)
      setSaved(true)
    },
    onError: (error) => {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
    },
  })

  function toggleDay(day: Day, checked: boolean) {
    setSaved(false)
    setDays((current) => (checked ? [...current, day] : current.filter((item) => item !== day)))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    setSaved(false)
    const result = validate(hostProfileSchema, { full_name: fullName, mobile_number: mobile })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    save.mutate({
      full_name: result.data.full_name,
      mobile_number: result.data.mobile_number,
      available_days: DAYS.filter((day) => days.includes(day)),
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
      <TextField
        label={t('field.fullName')}
        name="full_name"
        autoComplete="name"
        value={fullName}
        onChange={(value) => {
          setSaved(false)
          setFullName(value)
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
      <fieldset className="span-2 plain-fieldset">
        <legend>{t('hostProfile.days')}</legend>
        <div className="check-grid">
          {DAYS.map((day) => (
            <CheckboxField
              key={day}
              label={t(`days.${day}`)}
              name={`day_${day}`}
              checked={days.includes(day)}
              onChange={(checked) => toggleDay(day, checked)}
            />
          ))}
        </div>
      </fieldset>
      <button type="submit" className="btn btn-primary span-2" disabled={save.isPending}>
        {save.isPending ? t('common.saving') : t('common.save')}
      </button>
    </form>
  )
}

export default function HostProfilePage() {
  usePageTitle(t('hostProfile.title'))
  const query = useQuery({ queryKey: KEY, queryFn: getHostProfile })
  return (
    <>
      <h1>{t('hostProfile.title')}</h1>
      <p className="lead">{t('hostProfile.lead')}</p>
      <QueryBoundary query={query}>
        {(profile) => <HostProfileForm key={profile.id} profile={profile} />}
      </QueryBoundary>
    </>
  )
}
