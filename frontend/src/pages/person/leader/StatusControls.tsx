import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  fetchHomeGroups,
  fetchMembers,
  reconfirmPerson,
  reinstatePerson,
  revokePerson,
} from '../../../api/person'
import type { PersonDetail } from '../../../api/types'
import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { ApiError } from '../../../api/http'
import { errorMessage } from '../../../shared/errors'
import { Alert, SelectField } from '../../../shared/ui'
import { leaderProblem } from './problems'

/** What the page shows of a person after a change: the answer of the server, applied in place. */
export type Change = Partial<
  Pick<PersonDetail, 'status' | 'home_group' | 'flagged_for_recheck' | 'requested_status'>
>

const LEADS = ['verifier', 'admin', 'owner']

/** The words for a refused status change; a VERIFIER's revocation has two of its own. */
function revokeProblem(error: unknown): string {
  if (error instanceof ApiError && error.code === 'successor_required') {
    return t('leader.revoke.needSuccessor')
  }
  if (error instanceof ApiError && error.code === 'successor_not_member') {
    return t('admin.error.notMember')
  }
  return leaderProblem(error)
}

/** Revoke (after asking), reinstate a revoked person into a group of their church, or confirm a
 *  flagged status. The server decides who may; this only hides what cannot work. A VERIFIER is
 *  revoked by an ADMIN or the OWNER together with their successor; an ADMIN is replaced by the
 *  OWNER, on the screens of the OWNER. */
export default function StatusControls({
  person,
  onDone,
}: {
  person: PersonDetail
  onDone: (message: string, change: Change) => void
}) {
  const queryClient = useQueryClient()
  const actor = usePerson()
  const name = person.full_name
  const isVerifier = person.status === 'verifier'
  const actorIsAdmin = actor.status === 'admin' || actor.status === 'owner'
  const refresh = async () => {
    for (const key of ['applicants', 'members', 'revoked', 'flagged', 'church-groups'])
      await queryClient.invalidateQueries({ queryKey: [key] })
  }
  const [confirming, setConfirming] = useState(false)
  const [successor, setSuccessor] = useState('')
  const [group, setGroup] = useState('')
  const [to, setTo] = useState<'searcher' | 'provider'>('searcher')

  const revoke = useMutation({
    mutationFn: () => revokePerson(person.id, isVerifier && successor ? successor : undefined),
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
  // The members who could lead the group of a VERIFIER who is revoked.
  const members = useQuery({
    queryKey: ['members', 1, '', person.home_group?.id ?? ''],
    queryFn: () => fetchMembers(1, undefined, person.home_group?.id),
    enabled: confirming && isVerifier && !!person.home_group,
  })
  const others = (members.data?.items ?? []).filter((m) => m.id !== person.id)
  const needsSuccessor = isVerifier && (members.isPending || members.isError || others.length > 0)
  const busy = revoke.isPending || reinstate.isPending || reconfirm.isPending
  const failure = revoke.error ?? reinstate.error ?? reconfirm.error
  const canRevoke =
    !revoked &&
    person.status !== 'pending' &&
    (!LEADS.includes(person.status) || (isVerifier && actorIsAdmin))

  return (
    <div className="form-grid">
      {failure && (
        <Alert kind="error" focus>
          {revokeProblem(failure)}
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

      {!revoked && LEADS.includes(person.status) && person.status !== 'owner' && !canRevoke && (
        <p className="hint span-2">
          {isVerifier ? t('leader.revoke.adminOnly', { name }) : t('leader.revoke.leads', { name })}
        </p>
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
            <p>
              {isVerifier
                ? t('leader.revoke.warningLeader', { name })
                : t('leader.revoke.warning', { name })}
            </p>
            {isVerifier && members.isPending && (
              <p role="status" className="muted">
                {t('loading')}
              </p>
            )}
            {isVerifier && members.isError && (
              <Alert kind="error">
                <p>{errorMessage(members.error)}</p>
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => void members.refetch()}
                >
                  {t('common.retry')}
                </button>
              </Alert>
            )}
            {isVerifier && members.isSuccess && members.data.total > members.data.items.length && (
              <p className="hint">
                {t('admin.groups.more', {
                  count: members.data.items.length,
                  total: members.data.total,
                })}
              </p>
            )}
            {isVerifier && members.isSuccess && others.length === 0 && (
              <p className="hint">{t('leader.revoke.alone')}</p>
            )}
            {isVerifier && members.isSuccess && others.length > 0 && (
              <SelectField
                label={t('leader.revoke.successor')}
                name="revoke-successor"
                value={successor}
                onChange={setSuccessor}
                options={[
                  { value: '', label: t('leader.revoke.choose') },
                  ...others.map((m) => ({
                    value: m.id,
                    label: `${m.full_name} · ${t(`status.${m.status}`)}`,
                  })),
                ]}
              />
            )}
            <div className="form-actions">
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy || (needsSuccessor && !successor)}
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
