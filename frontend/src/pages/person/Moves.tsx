import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'

import { ApiError } from '../../api/http'
import {
  agreeToMove,
  askToMove,
  cancelMove,
  fetchHomeGroups,
  fetchMoves,
  LEADER_PAGE_SIZE,
} from '../../api/person'
import type { MoveRequest } from '../../api/types'
import { usePerson } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { PERSON_HOME } from '../../portals/config'
import { formatDate } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, Pager, QueryBoundary, SelectField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { leadsOwnGroup } from './leads'

/** What a refused move means. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'request_open') return t('moves.error.open')
    if (error.code === 'not_open') return t('moves.error.notOpen')
    if (error.code === 'already_agreed') return t('moves.error.agreed')
    if (error.code === 'request_stale') return t('moves.error.stale')
    if (error.code === 'invalid_choice') return t('moves.error.same')
    if (error.code === 'leads_a_group') return t('moves.ask.leads')
  }
  return errorMessage(error)
}

/** Move to another group of the church by agreement: the member asks (which is their own
 *  agreement) and the leaders of both groups agree. A leader hands their group on first. */
export default function Moves() {
  const person = usePerson()
  usePageTitle(t('moves.title'))
  if (person.status === 'pending' || person.status === 'revoked') {
    return <Navigate to={PERSON_HOME} replace />
  }
  return (
    <div className="container">
      <div className="card">
        <h1>{t('moves.title')}</h1>
        <p className="lead">{t('moves.lead')}</p>
        <AskForm />
      </div>
      <div className="card">
        <h2>{t('moves.list')}</h2>
        <MoveList />
      </div>
    </div>
  )
}

function AskForm() {
  const person = usePerson()
  const queryClient = useQueryClient()
  const [group, setGroup] = useState('')
  const [done, setDone] = useState(false)
  const groups = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
  })
  const ask = useMutation({
    mutationFn: () => askToMove(group),
    onSuccess: async () => {
      setGroup('')
      setDone(true)
      await queryClient.invalidateQueries({ queryKey: ['moves'] })
    },
  })
  const others = (groups.data?.items ?? []).filter((g) => g.id !== person.home_group?.id)
  if (leadsOwnGroup(person)) return <p className="hint">{t('moves.ask.leads')}</p>
  if (groups.isError) {
    return (
      <Alert kind="error">
        <p>{errorMessage(groups.error)}</p>
        <button type="button" className="btn btn-quiet" onClick={() => void groups.refetch()}>
          {t('common.retry')}
        </button>
      </Alert>
    )
  }
  if (groups.isPending) {
    return (
      <p role="status" className="muted">
        {t('loading')}
      </p>
    )
  }
  if (groups.data && others.length === 0) return <p className="muted">{t('moves.ask.none')}</p>
  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault()
        setDone(false)
        if (group) ask.mutate()
      }}
    >
      {done && (
        <Alert kind="success" focus>
          {t('moves.ask.done')}
        </Alert>
      )}
      {ask.error && (
        <Alert kind="error" focus>
          {problem(ask.error)}
        </Alert>
      )}
      <SelectField
        label={t('moves.ask.to')}
        name="move-to"
        value={group}
        onChange={setGroup}
        options={[
          { value: '', label: t('moves.ask.choose') },
          ...others.map((g) => ({ value: g.id, label: g.name })),
        ]}
      />
      <div className="form-actions span-2">
        <button type="submit" className="btn btn-primary" disabled={ask.isPending || !group}>
          {t('moves.ask.submit')}
        </button>
      </div>
    </form>
  )
}

function MoveList() {
  const [page, setPage] = useState(1)
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['moves', page],
    queryFn: () => fetchMoves(page),
    refetchInterval: 60_000,
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
            <p className="muted">{t('moves.none')}</p>
          ) : (
            <ul className="plain-list">
              {data.items.map((move) => (
                <li key={move.id}>
                  <Row move={move} onDone={setDone} />
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

function Row({ move, onDone }: { move: MoveRequest; onDone: (message: string) => void }) {
  const person = usePerson()
  const queryClient = useQueryClient()
  const open = move.state === 'open'
  // A leader acts for the group they lead: the one the member leaves or the one they join.
  const mine = person.home_group?.id
  const leads = leadsOwnGroup(person) && !!mine
  const leavesMine = leads && mine === move.from_group.id
  const joinsMine = leads && mine === move.to_group.id
  const canAgree =
    open && ((leavesMine && !move.agreed.from_leader) || (joinsMine && !move.agreed.to_leader))
  const canCancel = open && (move.person.id === person.id || leavesMine || joinsMine)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['moves'] })
    await queryClient.invalidateQueries({ queryKey: ['members'] })
  }
  const agree = useMutation({
    mutationFn: () => {
      cancel.reset()
      return agreeToMove(move.id)
    },
    onSuccess: async (result) => {
      await refresh()
      onDone(
        result.state === 'completed'
          ? t('moves.moved', { name: move.person.name })
          : t('moves.agreed', { name: move.person.name }),
      )
    },
  })
  const cancel = useMutation({
    mutationFn: () => {
      agree.reset()
      return cancelMove(move.id)
    },
    onSuccess: async () => {
      await refresh()
      onDone(t('moves.cancelled'))
    },
  })
  const busy = agree.isPending || cancel.isPending
  // Only the latest attempt's error is shown.
  const failure = cancel.isError ? cancel.error : agree.error
  return (
    <div>
      <p>
        <strong>
          {t('moves.row', {
            name: move.person.name,
            from: move.from_group.name,
            to: move.to_group.name,
          })}
        </strong>
        {' · '}
        {t(`moves.state.${move.state}`)}
        {' · '}
        <time dateTime={move.created_at}>{formatDate(move.created_at)}</time>
      </p>
      {open && (
        <ul className="plain-list">
          <li>{t('moves.agreed.person')}</li>
          <li>{move.agreed.from_leader ? t('moves.agreed.from') : t('moves.waiting.from')}</li>
          <li>{move.agreed.to_leader ? t('moves.agreed.to') : t('moves.waiting.to')}</li>
        </ul>
      )}
      {failure && (
        <Alert kind="error" focus>
          {problem(failure)}
        </Alert>
      )}
      {(canAgree || canCancel) && (
        <div className="form-actions">
          {canAgree && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => agree.mutate()}
            >
              {t('moves.agree', { name: move.person.name })}
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              className="btn btn-quiet"
              disabled={busy}
              onClick={() => cancel.mutate()}
            >
              {t('moves.cancel', { name: move.person.name })}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
