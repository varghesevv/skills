import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { ApiError } from '../../../api/http'
import {
  cancelChurchInvitation,
  closeChurch,
  fetchMembers,
  fetchChurchInvitations,
  fetchOwnerChurches,
  inviteAdmin,
  replaceAdmin,
  LEADER_PAGE_SIZE,
} from '../../../api/person'
import type { ChurchInvitation, ChurchInvitationCreated, OwnerChurch } from '../../../api/types'
import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { INVITE_LINK_PREFIX } from '../../../portals/config'
import { formatDate } from '../../../shared/dates'
import { errorMessage } from '../../../shared/errors'
import { Alert, Pager, QueryBoundary, SelectField, TextField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

/** The address an invited ADMIN opens. The token is the last part and travels only there. */
export function inviteUrl(token: string): string {
  return `${window.location.origin}${INVITE_LINK_PREFIX}${token}`
}

/** What a refused action means for the OWNER. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'church_name_taken') return t('owner.error.nameTaken')
    if (error.code === 'invitation_exists') return t('owner.error.invited')
    if (error.code === 'account_exists') return t('owner.error.account')
    if (error.code === 'owner_church') return t('owner.error.own')
    if (error.code === 'state_changed') return t('owner.error.changed')
    if (error.code === 'successor_not_member') return t('owner.error.notMember')
    if (error.code === 'invalid_choice') return t('owner.error.adminChoice')
    if (error.code === 'status_not_allowed') return t('owner.error.notAllowed')
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
  const [replacing, setReplacing] = useState(false)
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
        <div className="form-actions">
          <ReplaceAdmin church={church} open={replacing} setOpen={setReplacing} onDone={onDone} />
          {!replacing && (
            <button type="button" className="btn btn-quiet" onClick={() => setConfirming(true)}>
              {t('owner.churches.close', { church: church.name })}
            </button>
          )}
        </div>
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

/** The OWNER replaces the ADMIN of another church with one of its members. */
function ReplaceAdmin({
  church,
  open,
  setOpen,
  onDone,
}: {
  church: OwnerChurch
  open: boolean
  setOpen: (open: boolean) => void
  onDone: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [successor, setSuccessor] = useState('')
  const [groupSuccessor, setGroupSuccessor] = useState('')
  const [former, setFormer] = useState<'provider' | 'searcher'>('provider')
  const members = useQuery({
    queryKey: ['members', 1, '', '', church.id],
    queryFn: () => fetchMembers(1, undefined, undefined, church.id),
    enabled: open,
  })
  const replace = useMutation({
    mutationFn: () =>
      replaceAdmin(church.id, successor, former, groupSuccessor ? groupSuccessor : undefined),
    onSuccess: async (result) => {
      setOpen(false)
      setSuccessor('')
      setGroupSuccessor('')
      setFormer('provider')
      onDone(
        t('owner.admin.done', { name: result.admin.name, church: result.church.name }) +
          (result.former_admin_keeps_leading
            ? ` ${t('owner.admin.keeps', { old: church.admin_name })}`
            : ''),
      )
      await queryClient.invalidateQueries({ queryKey: ['owner-churches'] })
      await queryClient.invalidateQueries({ queryKey: ['members'] })
    },
  })
  // Dropping the form drops what was chosen and any refusal with it.
  const close = () => {
    replace.reset()
    setSuccessor('')
    setGroupSuccessor('')
    setFormer('provider')
    setOpen(false)
  }
  // The old ADMIN is not a choice for the new one.
  const others = (members.data?.items ?? []).filter((m) => m.id !== church.admin_id)
  // The leader of their group is one of its members: the old ADMIN's row says which group.
  const oldAdmin = (members.data?.items ?? []).find((m) => m.id === church.admin_id)
  // Without their row (a long list is cut at the first page) nobody is offered: the server
  // refuses a leader from another group, and "nobody" is what an ADMIN alone in it needs.
  const inTheirGroup = oldAdmin?.home_group
    ? others.filter((m) => m.home_group?.id === oldAdmin.home_group?.id)
    : []
  const options = (rows: typeof others, none?: string) => [
    { value: '', label: none ?? t('owner.admin.choose') },
    ...rows.map((m) => ({ value: m.id, label: `${m.full_name} · ${t(`status.${m.status}`)}` })),
  ]
  if (!open) {
    return (
      <button type="button" className="btn btn-quiet" onClick={() => setOpen(true)}>
        {t('owner.admin.replace', { church: church.name })}
      </button>
    )
  }
  return (
    <form
      className="form-grid span-2"
      aria-label={t('owner.admin.replace', { church: church.name })}
      onSubmit={(event) => {
        event.preventDefault()
        if (successor) replace.mutate()
      }}
    >
      {replace.error && (
        <Alert kind="error" focus>
          {problem(replace.error)}
        </Alert>
      )}
      {members.isPending && (
        <p role="status" className="muted span-2">
          {t('loading')}
        </p>
      )}
      {members.isError && (
        <Alert kind="error">
          <p>{errorMessage(members.error)}</p>
          <button type="button" className="btn btn-quiet" onClick={() => void members.refetch()}>
            {t('common.retry')}
          </button>
        </Alert>
      )}
      {members.isSuccess && others.length === 0 && (
        <p className="muted span-2">{t('owner.admin.nobody')}</p>
      )}
      {members.isSuccess && others.length > 0 && (
        <>
          {members.data.total > members.data.items.length && (
            <p className="hint span-2">
              {t('owner.admin.more', {
                count: members.data.items.length,
                total: members.data.total,
              })}
            </p>
          )}
          <SelectField
            label={t('owner.admin.successor')}
            name={`successor-${church.id}`}
            value={successor}
            onChange={setSuccessor}
            options={options(others)}
          />
          <SelectField
            label={t('owner.admin.former')}
            name={`former-${church.id}`}
            value={former}
            onChange={(value) => setFormer(value as 'provider' | 'searcher')}
            options={[
              { value: 'provider', label: t('admin.groups.former.provider') },
              { value: 'searcher', label: t('admin.groups.former.searcher') },
            ]}
          />
          <SelectField
            label={t('owner.admin.group')}
            name={`group-${church.id}`}
            value={groupSuccessor}
            onChange={setGroupSuccessor}
            options={options(inTheirGroup, t('owner.admin.groupNone'))}
          />
          <div className="form-actions span-2">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={replace.isPending || !successor}
            >
              {t('owner.admin.submit')}
            </button>
            <button type="button" className="btn btn-quiet" onClick={close}>
              {t('common.cancel')}
            </button>
          </div>
        </>
      )}
      {(!members.isSuccess || others.length === 0) && (
        <div className="form-actions span-2">
          <button type="button" className="btn btn-quiet" onClick={close}>
            {t('common.cancel')}
          </button>
        </div>
      )}
    </form>
  )
}
