import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchMe } from '../../../api/auth'
import { ApiError } from '../../../api/http'
import {
  acceptHandover,
  cancelHandover,
  fetchHandover,
  fetchMembers,
  fetchOwnerChurches,
  proposeHandover,
} from '../../../api/person'
import type { Handover } from '../../../api/types'
import { useAuth, usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { PERSON_HOME } from '../../../portals/config'
import { errorMessage } from '../../../shared/errors'
import { setFlash } from '../../../shared/flash'
import { Alert, QueryBoundary, SelectField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'
import { leadsOwnGroup } from '../leads'

/** What a refused handover action means. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'handover_open') return t('handover.error.open')
    if (error.code === 'invalid_choice') return t('handover.error.choice')
    if (error.code === 'successor_required') return t('handover.error.successor')
    if (error.code === 'successor_not_member') return t('handover.error.member')
    if (error.code === 'state_changed') return t('handover.error.changed')
    if (error.code === 'not_open') return t('handover.error.decided')
  }
  return errorMessage(error)
}

/** The handover of the OWNER role: the OWNER proposes it to the ADMIN of another church, who
 *  accepts (or either side cancels). Nothing changes until it is accepted. */
export default function HandoverPage() {
  const person = usePerson()
  usePageTitle(t('handover.title'))
  const current = useQuery({ queryKey: ['handover'], queryFn: fetchHandover })
  const isOwner = person.status === 'owner'
  return (
    <div className="container">
      <div className="card">
        <h1>{t('handover.title')}</h1>
        <p className="lead">{isOwner ? t('handover.leadOwner') : t('handover.leadAdmin')}</p>
        <QueryBoundary query={current}>
          {(data) =>
            data.request ? (
              <Waiting request={data.request} />
            ) : isOwner ? (
              <Propose />
            ) : (
              <p className="muted">{t('handover.none')}</p>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}

function Waiting({ request }: { request: Handover }) {
  const person = usePerson()
  const { setPerson } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const mine = request.owner.id === person.id
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['handover'] })
  const cancel = useMutation({
    mutationFn: () => cancelHandover(request.id),
    onSuccess: async () => {
      setDone(mine ? t('handover.cancelled') : t('handover.declined'))
      await refresh()
    },
  })
  const accept = useMutation({
    mutationFn: () => acceptHandover(request.id),
    onSuccess: async (result) => {
      await refresh()
      // They are the OWNER now: say so on the home, then reload who they are.
      setFlash(
        t('handover.accepted', {
          name: result.former_owner.name,
          status: result.former_owner_status,
        }),
      )
      let me = null
      try {
        const fresh = await fetchMe()
        if (fresh.user_type === 'person') me = fresh
      } catch {
        /* the next page load shows it */
      }
      navigate(PERSON_HOME, { replace: true })
      if (me) setPerson(me)
    },
  })
  const busy = cancel.isPending || accept.isPending
  const failure = cancel.error ?? accept.error
  const nobody = t('handover.waiting.nobody')
  if (done) {
    return (
      <Alert kind="success" focus>
        {done}
      </Alert>
    )
  }
  return (
    <div>
      <h2>{t('handover.waiting')}</h2>
      <p>
        {mine
          ? t('handover.waiting.owner', { name: request.new_owner.name })
          : t('handover.waiting.admin', { name: request.owner.name })}
      </p>
      <ul className="plain-list">
        <li>
          {t('handover.waiting.admins', {
            name: request.owner.name,
            successor: request.successor_admin?.name ?? nobody,
          })}
        </li>
        <li>
          {t('handover.waiting.leaders', {
            name: request.owner.name,
            successor: request.successor_leader?.name ?? nobody,
          })}
        </li>
        <li>
          {t('handover.waiting.former', {
            name: request.owner.name,
            status: request.former_owner_status,
          })}
        </li>
      </ul>
      {failure && (
        <Alert kind="error" focus>
          {problem(failure)}
        </Alert>
      )}
      {!confirming ? (
        <div className="form-actions">
          {!mine && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => setConfirming(true)}
            >
              {t('handover.accept')}
            </button>
          )}
          <button
            type="button"
            className="btn btn-quiet"
            disabled={busy}
            onClick={() => cancel.mutate()}
          >
            {mine ? t('handover.cancel') : t('handover.decline')}
          </button>
        </div>
      ) : (
        <div role="group" aria-label={t('handover.accept')}>
          <p>{t('handover.acceptWarning')}</p>
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => accept.mutate()}
            >
              {t('handover.acceptConfirm')}
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
      )}
    </div>
  )
}

function Propose() {
  const person = usePerson()
  const queryClient = useQueryClient()
  const [newOwner, setNewOwner] = useState('')
  const [admin, setAdmin] = useState('')
  const [leader, setLeader] = useState('')
  const [former, setFormer] = useState<'provider' | 'searcher'>('provider')
  const [sent, setSent] = useState<string | null>(null)
  const leads = leadsOwnGroup(person)
  const churches = useQuery({
    queryKey: ['owner-churches', 1],
    queryFn: () => fetchOwnerChurches(1),
  })
  const churchMembers = useQuery({
    queryKey: ['members', 1, '', '', person.church.id],
    queryFn: () => fetchMembers(1, undefined, undefined, person.church.id),
  })
  const groupMembers = useQuery({
    queryKey: ['members', 1, '', person.home_group?.id ?? ''],
    queryFn: () => fetchMembers(1, undefined, person.home_group?.id),
    enabled: leads,
  })
  const propose = useMutation({
    mutationFn: () =>
      proposeHandover({
        new_owner_id: newOwner,
        ...(admin ? { successor_admin_id: admin } : {}),
        ...(leads && leader ? { successor_leader_id: leader } : {}),
        former_owner_status: former,
      }),
    onSuccess: async () => {
      const chosen = candidates.find((c) => c.admin_id === newOwner)
      setSent(t('handover.sent', { name: chosen?.admin_name ?? '' }))
      await queryClient.invalidateQueries({ queryKey: ['handover'] })
    },
  })
  const candidates = (churches.data?.items ?? []).filter(
    (c) => c.open && c.admin_id && c.id !== person.church.id,
  )
  const adminChoices = (churchMembers.data?.items ?? []).filter((m) => m.id !== person.id)
  const leaderChoices = (groupMembers.data?.items ?? []).filter((m) => m.id !== person.id)
  const loading = churches.isPending || churchMembers.isPending || (leads && groupMembers.isPending)
  const failed = [churches, churchMembers, ...(leads ? [groupMembers] : [])].find((q) => q.isError)
  const needsAdmin = adminChoices.length > 0
  const needsLeader = leads && leaderChoices.length > 0
  const ready =
    !!newOwner && (!needsAdmin || !!admin) && (!needsLeader || !!leader) && !propose.isPending
  const options = (rows: typeof adminChoices) => [
    { value: '', label: t('handover.choose') },
    ...rows.map((m) => ({ value: m.id, label: `${m.full_name} · ${t(`status.${m.status}`)}` })),
  ]

  if (sent) {
    return (
      <Alert kind="success" focus>
        {sent}
      </Alert>
    )
  }
  if (loading) {
    return (
      <p role="status" className="muted">
        {t('loading')}
      </p>
    )
  }
  if (failed) {
    return (
      <Alert kind="error">
        <p>{errorMessage(failed.error)}</p>
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => {
            void churches.refetch()
            void churchMembers.refetch()
            if (leads) void groupMembers.refetch()
          }}
        >
          {t('common.retry')}
        </button>
      </Alert>
    )
  }
  if (candidates.length === 0) return <p className="muted">{t('handover.new.none')}</p>
  const cut = (data: { total: number; items: unknown[] } | undefined) =>
    data && data.total > data.items.length ? (
      <p className="hint span-2">
        {t('handover.more', { count: data.items.length, total: data.total })}
      </p>
    ) : null
  return (
    <form
      className="form-grid"
      aria-label={t('handover.title')}
      onSubmit={(event) => {
        event.preventDefault()
        if (ready) propose.mutate()
      }}
    >
      {propose.error && (
        <Alert kind="error" focus>
          {problem(propose.error)}
        </Alert>
      )}
      <SelectField
        label={t('handover.new')}
        name="new-owner"
        value={newOwner}
        onChange={setNewOwner}
        options={[
          { value: '', label: t('handover.new.choose') },
          ...candidates.map((c) => ({
            value: c.admin_id ?? '',
            label: `${c.admin_name} · ${c.name}`,
          })),
        ]}
      />
      {needsAdmin ? (
        <SelectField
          label={t('handover.newAdmin')}
          name="successor-admin"
          value={admin}
          onChange={setAdmin}
          options={options(adminChoices)}
        />
      ) : (
        <p className="hint span-2">{t('handover.alone')}</p>
      )}
      {cut(churchMembers.data)}
      {leads && needsLeader && (
        <SelectField
          label={t('handover.newLeader')}
          name="successor-leader"
          value={leader}
          onChange={setLeader}
          options={options(leaderChoices)}
        />
      )}
      {leads && cut(groupMembers.data)}
      {admin && (
        <SelectField
          label={t('handover.former')}
          name="former"
          value={former}
          onChange={(value) => setFormer(value as 'provider' | 'searcher')}
          options={[
            { value: 'provider', label: t('admin.groups.former.provider') },
            { value: 'searcher', label: t('admin.groups.former.searcher') },
          ]}
        />
      )}
      <div className="form-actions span-2">
        <button type="submit" className="btn btn-primary" disabled={!ready}>
          {t('handover.submit')}
        </button>
      </div>
    </form>
  )
}
