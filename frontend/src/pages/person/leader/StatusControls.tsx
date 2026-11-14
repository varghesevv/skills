import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  fetchHomeGroups,
  reconfirmPerson,
  reinstatePerson,
  revokePerson,
} from '../../../api/person'
import type { PersonDetail } from '../../../api/types'
import { t } from '../../../i18n'
import { Alert, SelectField } from '../../../shared/ui'
import { leaderProblem } from './problems'

/** What the page shows of a person after a change: the answer of the server, applied in place. */
export type Change = Partial<
  Pick<PersonDetail, 'status' | 'home_group' | 'flagged_for_recheck' | 'requested_status'>
>

const LEADS = ['verifier', 'admin', 'owner']

/** Revoke (after asking), reinstate a revoked person into a group of their church, or confirm a
 *  flagged status. The server decides who may; this only hides what cannot work. A leader is
 *  not revoked here: they are replaced first, on the screens of the ADMIN. */
export default function StatusControls({
  person,
  onDone,
}: {
  person: PersonDetail
  onDone: (message: string, change: Change) => void
}) {
  const queryClient = useQueryClient()
  const name = person.full_name
  const refresh = async () => {
    for (const key of ['applicants', 'members', 'revoked', 'flagged'])
      await queryClient.invalidateQueries({ queryKey: [key] })
  }
  const [confirming, setConfirming] = useState(false)
  const [group, setGroup] = useState('')
  const [to, setTo] = useState<'searcher' | 'provider'>('searcher')

  const revoke = useMutation({
    mutationFn: () => revokePerson(person.id),
    onSuccess: async () => {
      await refresh()
      setConfirming(false)
      onDone(t('leader.revoke.done', { name }), {
        status: 'revoked',
        home_group: null,
        flagged_for_recheck: false,
        requested_status: null,
      })
    },
  })
  const revoked = person.status === 'revoked'
  const groups = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
    enabled: revoked,
  })
  const chosenGroup = groups.data?.items.find((g) => g.id === group)
  const reinstate = useMutation({
    mutationFn: () => reinstatePerson(person.id, to, group),
    onSuccess: async (result) => {
      await refresh()
      onDone(t('leader.reinstate.done', { name }), {
        status: result.status,
        home_group: chosenGroup ? { id: chosenGroup.id, name: chosenGroup.name } : null,
      })
    },
  })
  const reconfirm = useMutation({
    mutationFn: () => reconfirmPerson(person.id),
    onSuccess: async (result) => {
      await refresh()
      onDone(t('leader.reconfirm.done', { name }), {
        flagged_for_recheck: result.flagged_for_recheck,
      })
    },
  })
  const busy = revoke.isPending || reinstate.isPending || reconfirm.isPending
  const failure = revoke.error ?? reinstate.error ?? reconfirm.error
  const canRevoke = !revoked && !LEADS.includes(person.status) && person.status !== 'pending'

  return (
    <div className="form-grid">
      {failure && (
        <Alert kind="error" focus>
          {leaderProblem(failure)}
        </Alert>
      )}

      {person.flagged_for_recheck && !revoked && (
        <div className="span-2">
          <p>{t('leader.reconfirm.text', { name })}</p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => reconfirm.mutate()}
          >
            {t('leader.reconfirm.submit', { name })}
          </button>
        </div>
      )}

      {revoked && (
        <form
          className="form-grid span-2"
          aria-label={t('leader.reinstate.title', { name })}
          onSubmit={(event) => {
            event.preventDefault()
            if (group) reinstate.mutate()
          }}
        >
          <h2 className="span-2">{t('leader.reinstate.title', { name })}</h2>
          {groups.data && groups.data.items.length === 0 ? (
            <p className="muted span-2">{t('leader.reinstate.noGroups')}</p>
          ) : (
            <>
              <SelectField
                label={t('leader.reinstate.group')}
                name="group"
                value={group}
                onChange={setGroup}
                options={[
                  { value: '', label: t('leader.reinstate.choose') },
                  ...(groups.data?.items ?? []).map((g) => ({ value: g.id, label: g.name })),
                ]}
              />
              <SelectField
                label={t('leader.reinstate.status')}
                name="to"
                value={to}
                onChange={(value) => setTo(value as 'searcher' | 'provider')}
                options={[
                  { value: 'searcher', label: t('status.searcher') },
                  { value: 'provider', label: t('status.provider') },
                ]}
              />
              <div className="form-actions span-2">
                <button type="submit" className="btn btn-primary" disabled={busy || !group}>
                  {t('leader.reinstate.submit', { name })}
                </button>
              </div>
            </>
          )}
        </form>
      )}

      {!revoked && LEADS.includes(person.status) && person.status !== 'owner' && (
        <p className="hint span-2">{t('leader.revoke.leads', { name })}</p>
      )}

      {canRevoke &&
        (!confirming ? (
          <div className="form-actions span-2">
            <button
              type="button"
              className="btn btn-quiet"
              disabled={busy}
              onClick={() => setConfirming(true)}
            >
              {t('leader.revoke.open', { name })}
            </button>
          </div>
        ) : (
          <div className="span-2" role="group" aria-label={t('leader.revoke.open', { name })}>
            <p>{t('leader.revoke.warning', { name })}</p>
            <div className="form-actions">
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => revoke.mutate()}
              >
                {t('leader.revoke.confirm')}
              </button>
              <button
                type="button"
                className="btn btn-quiet"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        ))}
    </div>
  )
}
