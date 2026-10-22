import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { getOrgProfile, updateOrgProfile } from '../../api/organisation'
import type { ApprovalStatus, OrgProfile } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { errorMessage, serverFieldErrors } from '../../shared/errors'
import { Alert, Badge, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { orgProfileSchema, validate, type FieldErrors } from '../../shared/validation'
import { ORG_PROFILE_KEY } from './keys'

export const APPROVAL_TEXT: Record<ApprovalStatus, StringKey> = {
  pending: 'orgProfile.status.pending',
  approved: 'orgProfile.status.approved',
  rejected: 'orgProfile.status.rejected',
}
export const APPROVAL_TONE: Record<ApprovalStatus, 'neutral' | 'good' | 'warn'> = {
  pending: 'warn',
  approved: 'good',
  rejected: 'neutral',
}

function OrgProfileForm({ profile }: { profile: OrgProfile }) {
  const queryClient = useQueryClient()
  const [orgName, setOrgName] = useState(profile.org_name)
  const [mobile, setMobile] = useState(profile.mobile_number)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: updateOrgProfile,
    onSuccess: (updated) => {
      queryClient.setQueryData(ORG_PROFILE_KEY, updated)
      setSaved(true)
    },
    onError: (error) => {
      setErrors(serverFieldErrors(error))
      setFormError(errorMessage(error))
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    setSaved(false)
    const result = validate(orgProfileSchema, { org_name: orgName, mobile_number: mobile })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    save.mutate(result.data)
  }

  return (
    <>
      <section className="card" aria-labelledby="approval-heading">
        <h2 id="approval-heading">{t('orgProfile.approval')}</h2>
        <p>
          <Badge tone={APPROVAL_TONE[profile.approval_status]}>
            {t(APPROVAL_TEXT[profile.approval_status])}
          </Badge>
        </p>
        <p className="muted">{profile.email}</p>
      </section>
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
          label={t('field.orgName')}
          name="org_name"
          autoComplete="organization"
          value={orgName}
          onChange={(value) => {
            setSaved(false)
            setOrgName(value)
          }}
          error={errors.org_name}
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
        <button type="submit" className="btn btn-primary span-2" disabled={save.isPending}>
          {save.isPending ? t('common.saving') : t('common.save')}
        </button>
      </form>
    </>
  )
}

export default function OrgProfilePage() {
  usePageTitle(t('orgProfile.title'))
  const query = useQuery({ queryKey: ORG_PROFILE_KEY, queryFn: getOrgProfile })
  return (
    <>
      <h1>{t('orgProfile.title')}</h1>
      <p className="lead">{t('orgProfile.lead')}</p>
      <QueryBoundary query={query}>
        {(profile) => (
          <div className="stack">
            <OrgProfileForm key={profile.id} profile={profile} />
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
