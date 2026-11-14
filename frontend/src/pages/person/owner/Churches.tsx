import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { ApiError } from '../../../api/http'
import {
  cancelChurchInvitation,
  closeChurch,
  fetchChurchInvitations,
  fetchOwnerChurches,
  inviteAdmin,
  LEADER_PAGE_SIZE,
} from '../../../api/person'
import type { ChurchInvitation, ChurchInvitationCreated, OwnerChurch } from '../../../api/types'
import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { formatDate } from '../../../shared/dates'
import { errorMessage } from '../../../shared/errors'
import { Alert, Pager, QueryBoundary, TextField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

/** The address an invited ADMIN opens. The token is the last part and travels only there. */
export function inviteUrl(token: string): string {
  return `${window.location.origin}/invite/${token}`
}

/** What a refused action means for the OWNER. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'church_name_taken') return t('owner.error.nameTaken')
    if (error.code === 'invitation_exists') return t('owner.error.invited')
    if (error.code === 'account_exists') return t('owner.error.account')
    if (error.code === 'owner_church') return t('owner.error.own')
    if (error.code === 'state_changed') return t('owner.error.changed')
  }
  return errorMessage(error)
}

/** The OWNER's view of every church, with the invitation of a new church's ADMIN and the closing
 *  of a church other than their own. */
export default function Churches() {
  usePageTitle(t('owner.churches.title'))
  return (
    <div className="container">
      <div className="card">
        <h1>{t('owner.churches.title')}</h1>
        <p className="lead">{t('owner.churches.lead')}</p>
        <InviteForm />
      </div>
      <div className="card">
        <h2>{t('owner.invitations.title')}</h2>
        <Invitations />
      </div>
      <div className="card">
        <ChurchList />
      </div>
    </div>
  )
}

function InviteForm() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [created, setCreated] = useState<ChurchInvitationCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const field = useRef<HTMLInputElement>(null)
  const invite = useMutation({
    mutationFn: () => inviteAdmin(name.trim(), email.trim()),
    onSuccess: async (result) => {
      setCreated(result)
      setCopied(false)
      setName('')
      setEmail('')
      await queryClient.invalidateQueries({ queryKey: ['church-invitations'] })
    },
  })
  const url = created ? inviteUrl(created.token) : ''

  async function copy() {
    field.current?.select()
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // Without clipboard access the link stays selected, so it can be copied by hand.
    }
  }

  return (
    <form
      className="form-grid"
      aria-label={t('owner.invite.title')}
      onSubmit={(event) => {
        event.preventDefault()
        setCreated(null)
        if (name.trim().length >= 2 && email.trim()) invite.mutate()
      }}
    >
      <h2 className="span-2">{t('owner.invite.title')}</h2>
      {invite.error && (
        <Alert kind="error" focus>
          {problem(invite.error)}
        </Alert>
      )}
      {created && (
        <div className="span-2">
          <Alert kind="success" focus>
            {t('owner.invite.once')}
          </Alert>
          <label className="field">
            <span className="field-label">{t('owner.invite.label')}</span>
            <input ref={field} readOnly value={url} onFocus={(e) => e.target.select()} />
          </label>
          <div className="form-actions">
            <button type="button" className="btn btn-primary" onClick={() => void copy()}>
              {copied ? t('owner.invite.copied') : t('owner.invite.copy')}
            </button>
          </div>
          <p className="hint">
            {t('owner.invite.expires', { date: formatDate(created.expires_at) })}
          </p>
        </div>
      )}
      <TextField
        label={t('owner.invite.name')}
        name="church_name"
        value={name}
        onChange={setName}
        maxLength={200}
      />
      <TextField
        label={t('owner.invite.email')}
        name="email"
        type="email"
        value={email}
        onChange={setEmail}
        autoComplete="off"
      />
      <div className="form-actions span-2">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={invite.isPending || name.trim().length < 2 || !email.trim()}
        >
          {t('owner.invite.submit')}
        </button>
      </div>
    </form>
  )
}

function Invitations() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['church-invitations', page],
    queryFn: () => fetchChurchInvitations(page),
  })
  const cancel = useMutation({
    mutationFn: (id: string) => cancelChurchInvitation(id),
    onSuccess: async () => {
      setDone(t('owner.invitations.cancelled'))
      await queryClient.invalidateQueries({ queryKey: ['church-invitations'] })
    },
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
          {cancel.error && (
            <Alert kind="error" focus>
              {problem(cancel.error)}
            </Alert>
          )}
          {data.items.length === 0 ? (
            <p className="muted">{t('owner.invitations.none')}</p>
          ) : (
            <ul className="plain-list">
              {data.items.map((row: ChurchInvitation) => (
                <li key={row.id}>
                  {t('owner.invitations.row', { church: row.church_name, email: row.email })}
                  {' · '}
                  {row.expired
                    ? t('owner.invitations.expired', { date: formatDate(row.expires_at) })
                    : t('owner.invitations.until', { date: formatDate(row.expires_at) })}{' '}
                  <button
                    type="button"
                    className="btn btn-quiet"
                    disabled={cancel.isPending}
                    onClick={() => {
                      setDone(null)
                      cancel.mutate(row.id)
                    }}
                  >
                    {t('owner.invitations.cancel', { church: row.church_name })}
                  </button>
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

function ChurchList() {
  const [page, setPage] = useState(1)
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['owner-churches', page],
    queryFn: () => fetchOwnerChurches(page),
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
            <p className="muted">{t('owner.churches.none')}</p>
          ) : (
            <ul className="plain-list">
              {data.items.map((church) => (
                <li key={church.id}>
                  <ChurchRow church={church} onDone={setDone} />
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

function ChurchRow({ church, onDone }: { church: OwnerChurch; onDone: (message: string) => void }) {
  const person = usePerson()
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const own = church.id === person.church.id
  const close = useMutation({
    mutationFn: () => closeChurch(church.id),
    onSuccess: async (result) => {
      setConfirming(false)
      onDone(
        t('owner.churches.closed.done', {
          church: result.name,
          groups: String(result.closed_groups),
          accounts: String(result.closed_accounts),
        }),
      )
      await queryClient.invalidateQueries({ queryKey: ['owner-churches'] })
    },
  })
  return (
    <div>
      <h2>{church.name}</h2>
      <p>
        {t('owner.churches.row', { name: church.admin_name })}
        {' · '}
        {t('owner.churches.counts', {
          groups: String(church.groups),
          members: String(church.members),
          revoked: String(church.revoked),
        })}
        {own && <> · {t('owner.churches.yours')}</>}
        {church.closed_at && (
          <> · {t('owner.churches.closed', { date: formatDate(church.closed_at) })}</>
        )}
      </p>
      {close.error && (
        <Alert kind="error" focus>
          {problem(close.error)}
        </Alert>
      )}
      {church.open && !own && !confirming && (
        <button type="button" className="btn btn-quiet" onClick={() => setConfirming(true)}>
          {t('owner.churches.close', { church: church.name })}
        </button>
      )}
      {confirming && (
        <div role="group" aria-label={t('owner.churches.close', { church: church.name })}>
          <p>{t('owner.churches.closeWarning', { church: church.name })}</p>
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={close.isPending}
              onClick={() => close.mutate()}
            >
              {t('owner.churches.closeConfirm')}
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
    </div>
  )
}
