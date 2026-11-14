import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'

import { fetchMe } from '../../api/auth'
import {
  approveGroupRequest,
  askForGroup,
  declineGroupRequest,
  fetchGroupRequests,
  fetchMembers,
  LEADER_PAGE_SIZE,
} from '../../api/person'
import type { GroupRequest, MemberRow } from '../../api/types'
import { ApiError } from '../../api/http'
import { useAuth, usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { PERSON_HOME } from '../../portals/config'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, Pager, QueryBoundary, SelectField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

/** What a refused request means. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'group_name_taken') return t('groupRequests.error.taken')
    if (error.code === 'request_open') return t('groupRequests.error.open')
    if (error.code === 'successor_required') return t('groupRequests.error.successor')
    if (error.code === 'not_open') return t('groupRequests.error.decided')
    if (error.code === 'requester_unavailable') return t('groupRequests.error.gone')
  }
  return errorMessage(error)
}

/** Start a home group: a member asks, and the ADMIN of the church (or the OWNER) decides. An ADMIN
 *  or the OWNER start one at once. Whoever leads a group now says who leads it from now on. */
export default function GroupRequests() {
  const person = usePerson()
  usePageTitle(t('groupRequests.title'))
  if (person.status === 'pending' || person.status === 'revoked') {
    return <Navigate to={PERSON_HOME} replace />
  }
  const decides = person.status === 'admin' || person.status === 'owner'
  return (
    <div className="container">
      <div className="card">
        <h1>{t('groupRequests.title')}</h1>
        <p className="lead">{decides ? t('groupRequests.leadOwn') : t('groupRequests.lead')}</p>
        <AskForm decides={decides} />
      </div>
      <div className="card">
        <h2>{decides ? t('groupRequests.open') : t('groupRequests.yours')}</h2>
        <Requests decides={decides} />
      </div>
    </div>
  )
}

/** The members in the caller's scope who could lead a group, from the first page of the list. */
function useCandidates(enabled: boolean, groupId?: string) {
  return useQuery({
    queryKey: ['members', 1, '', groupId ?? ''],
    queryFn: () => fetchMembers(1, undefined, groupId),
    enabled,
    select: (data) => data.items,
  })
}

function candidateOptions(rows: MemberRow[] | undefined, none: boolean) {
  return [
    { value: '', label: none ? t('groupRequests.successorNone') : t('groupRequests.choose') },
    ...(rows ?? []).map((m) => ({
      value: m.id,
      label: m.home_group ? `${m.full_name} · ${m.home_group.name}` : m.full_name,
    })),
  ]
}

function AskForm({ decides }: { decides: boolean }) {
  const person = usePerson()
  const { setPerson } = useAuth()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [successor, setSuccessor] = useState('')
  const [done, setDone] = useState<string | null>(null)
  // The group they lead: an ADMIN or the OWNER may belong to a group someone else leads.
  const leads = decides && person.home_group !== null && person.leader?.name === person.full_name
  const candidates = useCandidates(leads, person.home_group?.id)
  const ask = useMutation({
    mutationFn: () => askForGroup(name.trim(), leads && successor ? successor : undefined),
    onSuccess: async (result) => {
      setName('')
      setSuccessor('')
      await queryClient.invalidateQueries({ queryKey: ['group-requests'] })
      await queryClient.invalidateQueries({ queryKey: ['members'] })
      if (result.group) {
        setDone(t('groupRequests.started', { name: result.group.name }))
        // The group exists now: a failure to refresh who I am must not look like a failed start.
        try {
          const me = await fetchMe()
          if (me.user_type === 'person') setPerson(me)
        } catch {
          /* the next page load shows the new group */
        }
      } else {
        setDone(t('groupRequests.asked'))
      }
    },
  })
  const own = (candidates.data ?? []).filter((m) => m.id !== person.id)
  // Someone must lead the group they leave, unless they are alone in it.
  const needsChoice = leads && (candidates.isPending || candidates.isError || own.length > 0)
  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault()
        setDone(null)
        if (name.trim().length >= 2) ask.mutate()
      }}
    >
      {done && (
        <Alert kind="success" focus>
          {done}
        </Alert>
      )}
      {ask.error && (
        <Alert kind="error" focus>
          {problem(ask.error)}
        </Alert>
      )}
      <TextField
        label={t('groupRequests.name')}
        name="group_name"
        value={name}
        onChange={setName}
        maxLength={200}
      />
      {leads && candidates.isError && (
        <Alert kind="error">
          <p>{errorMessage(candidates.error)}</p>
          <button type="button" className="btn btn-quiet" onClick={() => void candidates.refetch()}>
            {t('common.retry')}
          </button>
        </Alert>
      )}
      {leads && own.length > 0 && (
        <SelectField
          label={t('groupRequests.successor')}
          name="successor"
          value={successor}
          onChange={setSuccessor}
          options={candidateOptions(own, false)}
        />
      )}
      <div className="form-actions span-2">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={ask.isPending || name.trim().length < 2 || (needsChoice && !successor)}
        >
          {decides ? t('groupRequests.submitOwn') : t('groupRequests.submit')}
        </button>
      </div>
    </form>
  )
}

function Requests({ decides }: { decides: boolean }) {
  const [page, setPage] = useState(1)
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['group-requests', page],
    queryFn: () => fetchGroupRequests(page),
    refetchInterval: decides ? 60_000 : false,
  })
  return (
    <QueryBoundary query={list}>
      {(data) => (
        <>
          {done && (
            <Alert kind="success" focus>
              {done}
            </Alert>
          )}
          {data.items.length === 0 ? (
            <p className="muted">{t('groupRequests.none')}</p>
          ) : (
            <ul className="plain-list">
              {data.items.map((request) => (
                <li key={request.id}>
                  <Row request={request} decides={decides} onDone={setDone} />
                </li>
              ))}
            </ul>
          )}
          <Pager page={page} pageSize={LEADER_PAGE_SIZE} total={data.total} onChange={setPage} />
        </>
      )}
    </QueryBoundary>
  )
}

function Row({
  request,
  decides,
  onDone,
}: {
  request: GroupRequest
  decides: boolean
  onDone: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [successor, setSuccessor] = useState('')
  const open = request.state === 'open'
  const candidates = useCandidates(
    decides && open && request.requester_leads_a_group,
    request.requester_group?.id,
  )
  // Someone must take over the group the requester leaves, unless they are its only member.
  const others = (candidates.data ?? []).filter((m) => m.id !== request.requester.id)
  const needsChoice =
    request.requester_leads_a_group &&
    (candidates.isPending || candidates.isError || others.length > 0)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['group-requests'] })
    await queryClient.invalidateQueries({ queryKey: ['members'] })
  }
  const approve = useMutation({
    mutationFn: () => approveGroupRequest(request.id, successor || undefined),
    onSuccess: async (result) => {
      await refresh()
      onDone(t('groupRequests.approved', { name: result.group.name }))
    },
  })
  const decline = useMutation({
    mutationFn: () => declineGroupRequest(request.id),
    onSuccess: async () => {
      await refresh()
      onDone(t('groupRequests.declined'))
    },
  })
  const busy = approve.isPending || decline.isPending
  const failure = approve.error ?? decline.error
  return (
    <div>
      <p>
        <strong>{request.group_name}</strong>
        {decides && (
          <>
            {' '}
            · {t('groupRequests.by', { name: request.requester.name, group: request.group_name })}
            {' · '}
            {request.church.name}
          </>
        )}
        {' · '}
        {t(`groupRequests.state.${request.state}`)}
        {' · '}
        <time dateTime={request.created_at}>{formatDate(request.created_at)}</time>
      </p>
      {failure && (
        <Alert kind="error" focus>
          {problem(failure)}
        </Alert>
      )}
      {decides && open && (
        <div className="form-grid">
          {request.requester_leads_a_group && (
            <>
              <p className="hint span-2">
                {t('groupRequests.leads', { name: request.requester.name })}
              </p>
              {candidates.isError && (
                <Alert kind="error">
                  <p>{errorMessage(candidates.error)}</p>
                  <button
                    type="button"
                    className="btn btn-quiet"
                    onClick={() => void candidates.refetch()}
                  >
                    {t('common.retry')}
                  </button>
                </Alert>
              )}
              <SelectField
                label={t('groupRequests.successorOf', { name: request.requester.name })}
                name={`successor-${request.id}`}
                value={successor}
                onChange={setSuccessor}
                options={candidateOptions(others, candidates.isSuccess && others.length === 0)}
              />
            </>
          )}
          <div className="form-actions span-2">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || (needsChoice && !successor)}
              onClick={() => approve.mutate()}
            >
              {t('groupRequests.approve', { group: request.group_name })}
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              disabled={busy}
              onClick={() => decline.mutate()}
            >
              {t('groupRequests.decline', { group: request.group_name })}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
