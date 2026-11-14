import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchMe } from '../../../api/auth'
import { ApiError } from '../../../api/http'
import { closeGroup, fetchHomeGroups, type FormerLeaderStatus } from '../../../api/person'
import { useAuth, usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { Confirm, useReturnFocus } from '../../../shared/Confirm'
import { errorMessage } from '../../../shared/errors'
import { setFlash } from '../../../shared/flash'
import { Alert, SelectField } from '../../../shared/ui'
import { PERSON_HOME } from '../../../portals/config'
import { usePageTitle } from '../../../shared/usePageTitle'

function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'group_not_empty') return t('myGroup.error.notEmpty')
    if (error.code === 'invalid_choice') return t('myGroup.error.choice')
    if (error.code === 'state_changed') return t('leader.error.changed')
  }
  return errorMessage(error)
}

/** The leader's own group: close it when they are its last member, by joining another one. */
export default function MyGroup() {
  const person = usePerson()
  const { setPerson } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  usePageTitle(t('myGroup.title'))
  const group = person.home_group
  const [target, setTarget] = useState('')
  const keeps = person.status === 'admin' || person.status === 'owner'
  const [former, setFormer] = useState<FormerLeaderStatus>(keeps ? 'keep' : 'provider')
  const [confirming, setConfirming] = useState(false)
  const opener = useReturnFocus<HTMLButtonElement>(confirming)
  const groups = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
  })
  const close = useMutation({
    mutationFn: () => closeGroup(group?.id ?? '', target, keeps ? 'keep' : former),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['church-groups'] })
      await queryClient.invalidateQueries({ queryKey: ['members'] })
      // A VERIFIER is a provider or a searcher now, so this page is no longer theirs and its guard
      // would send them home without a word. Go home first with the outcome, then change who they
      // are: the notice is kept in the navigation state.
      let me = null
      try {
        const fresh = await fetchMe()
        if (fresh.user_type === 'person') me = fresh
      } catch {
        /* the next page load shows it */
      }
      setFlash(
        t('myGroup.close.done', {
          closed: result.closed_group.name,
          joined: result.joined_group.name,
        }),
      )
      navigate(PERSON_HOME, { replace: true })
      if (me) setPerson(me)
    },
  })
  const others = (groups.data?.items ?? []).filter((g) => g.id !== group?.id)
  const name = group?.name ?? ''
  return (
    <div className="container">
      <div className="card">
        <h1>{t('myGroup.title')}</h1>
        {group && (
          <>
            <p className="lead">{t('myGroup.lead', { group: name })}</p>
            {close.error && (
              <Alert kind="error" focus>
                {problem(close.error)}
              </Alert>
            )}
            {groups.isPending && (
              <p role="status" className="muted">
                {t('loading')}
              </p>
            )}
            {groups.isError && (
              <Alert kind="error">
                <p>{errorMessage(groups.error)}</p>
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => void groups.refetch()}
                >
                  {t('common.retry')}
                </button>
              </Alert>
            )}
            {groups.isSuccess && others.length === 0 && (
              <p className="muted">{t('myGroup.close.none')}</p>
            )}
            {groups.isSuccess && others.length > 0 && !confirming && (
              <form
                className="form-grid"
                aria-label={t('myGroup.close.title', { group: name })}
                onSubmit={(event) => {
                  event.preventDefault()
                  if (target) setConfirming(true)
                }}
              >
                <h2 className="span-2">{t('myGroup.close.title', { group: name })}</h2>
                <SelectField
                  label={t('myGroup.close.to')}
                  name="join"
                  value={target}
                  onChange={setTarget}
                  options={[
                    { value: '', label: t('myGroup.close.choose') },
                    ...others.map((g) => ({ value: g.id, label: g.name })),
                  ]}
                />
                {!keeps && (
                  <SelectField
                    label={t('myGroup.close.former')}
                    name="former"
                    value={former}
                    onChange={(value) => setFormer(value as FormerLeaderStatus)}
                    options={[
                      { value: 'provider', label: t('admin.groups.former.provider') },
                      { value: 'searcher', label: t('admin.groups.former.searcher') },
                    ]}
                  />
                )}
                <div className="form-actions span-2">
                  <button ref={opener} type="submit" className="btn btn-quiet" disabled={!target}>
                    {t('myGroup.close.submit', { group: name })}
                  </button>
                </div>
              </form>
            )}
            {confirming && (
              <Confirm
                label={t('myGroup.close.title', { group: name })}
                warning={t('myGroup.close.warning', { group: name })}
                confirmLabel={t('myGroup.close.confirm')}
                busy={close.isPending}
                onConfirm={() => close.mutate()}
                onCancel={() => setConfirming(false)}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
