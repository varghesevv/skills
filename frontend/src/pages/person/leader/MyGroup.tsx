import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { fetchMe } from '../../../api/auth'
import { ApiError } from '../../../api/http'
import { closeGroup, fetchHomeGroups, type FormerLeaderStatus } from '../../../api/person'
import { useAuth, usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { errorMessage } from '../../../shared/errors'
import { Alert, SelectField } from '../../../shared/ui'
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
  usePageTitle(t('myGroup.title'))
  const group = person.home_group
  const [target, setTarget] = useState('')
  const keeps = person.status === 'admin' || person.status === 'owner'
  const [former, setFormer] = useState<FormerLeaderStatus>(keeps ? 'keep' : 'provider')
  const [confirming, setConfirming] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const groups = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
  })
  const close = useMutation({
    mutationFn: () => closeGroup(group?.id ?? '', target, keeps ? 'keep' : former),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['church-groups'] })
      await queryClient.invalidateQueries({ queryKey: ['members'] })
      setConfirming(false)
      setDone(
        t('myGroup.close.done', {
          closed: result.closed_group.name,
          joined: result.joined_group.name,
        }),
      )
      // They lead no group now, so who they are changed too.
      try {
        const me = await fetchMe()
        if (me.user_type === 'person') setPerson(me)
      } catch {
        /* the next page load shows it */
      }
    },
  })
  const others = (groups.data?.items ?? []).filter((g) => g.id !== group?.id)
  const name = group?.name ?? ''
  return (
    <div className="container">
      <div className="card">
        <h1>{t('myGroup.title')}</h1>
        {done && (
          <Alert kind="success" focus>
            {done}
          </Alert>
        )}
        {!done && group && (
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
                  <button type="submit" className="btn btn-quiet" disabled={!target}>
                    {t('myGroup.close.submit', { group: name })}
                  </button>
                </div>
              </form>
            )}
            {confirming && (
              <div role="group" aria-label={t('myGroup.close.title', { group: name })}>
                <p>{t('myGroup.close.warning', { group: name })}</p>
                <div className="form-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={close.isPending}
                    onClick={() => close.mutate()}
                  >
                    {t('myGroup.close.confirm')}
                  </button>
                  <button
                    type="button"
                    className="btn btn-quiet"
                    disabled={close.isPending}
                    onClick={() => setConfirming(false)}
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
