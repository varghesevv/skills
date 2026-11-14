import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import {
  endGroupInvitation,
  fetchGroupInvitations,
  makeGroupInvitation,
  type GroupInvitationCreated,
} from '../../../api/person'
import { ApiError } from '../../../api/http'
import { t } from '../../../i18n'
import { JOIN_LINK_PREFIX } from '../../../portals/config'
import { formatDate } from '../../../shared/dates'
import { errorMessage } from '../../../shared/errors'
import { Alert, QueryBoundary } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

const KEY = ['group-invitations']

/** The address people open to sign up into the group. The token is the last part and travels only
 *  there: it is never in a list, a request address or a log line of this app. */
export function joinUrl(token: string): string {
  return `${window.location.origin}${JOIN_LINK_PREFIX}${token}`
}

function problem(error: unknown): string {
  if (error instanceof ApiError && error.code === 'no_home_group') {
    return t('invitations.error.noGroup')
  }
  return errorMessage(error)
}

/** The leader makes links to their group, sees the ones that work, and ends one. */
export default function GroupInvitations() {
  usePageTitle(t('invitations.title'))
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: KEY, queryFn: fetchGroupInvitations })
  const [created, setCreated] = useState<GroupInvitationCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [ended, setEnded] = useState(false)
  const field = useRef<HTMLInputElement>(null)
  const make = useMutation({
    mutationFn: makeGroupInvitation,
    onMutate: () => {
      setEnded(false)
      end.reset()
    },
    onSuccess: async (result) => {
      setCreated(result)
      setCopied(false)
      await queryClient.invalidateQueries({ queryKey: KEY })
    },
  })
  const end = useMutation({
    mutationFn: (id: string) => endGroupInvitation(id),
    onMutate: () => {
      setEnded(false)
      make.reset()
    },
    // A refused ending (the link expired or ended elsewhere) leaves the list stale as well.
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
    onSuccess: (_none, id) => {
      // The link that was just made is gone from the screen when it is the one that ended.
      if (created?.id === id) setCreated(null)
      setEnded(true)
    },
  })
  const url = created ? joinUrl(created.token) : ''

  async function copy() {
    field.current?.select()
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // Without clipboard access the link stays selected, so it can be copied by hand.
    }
  }

  const failure = make.error ?? end.error
  return (
    <div className="container">
      <div className="card">
        <h1>{t('invitations.title')}</h1>
        <p className="lead">{t('invitations.lead')}</p>
        {failure && (
          <Alert kind="error" focus>
            {problem(failure)}
          </Alert>
        )}
        {ended && !failure && (
          <Alert kind="success" focus>
            {t('invitations.revoked')}
          </Alert>
        )}
        {created && (
          <div>
            <Alert kind="success" focus>
              {t('invitations.once')}
            </Alert>
            <label className="field">
              <span className="field-label">{t('invitations.label')}</span>
              <input ref={field} readOnly value={url} onFocus={(e) => e.target.select()} />
            </label>
            <div className="form-actions">
              <button type="button" className="btn btn-primary" onClick={() => void copy()}>
                {copied ? t('invitations.copied') : t('invitations.copy')}
              </button>
            </div>
            <p className="hint">
              {t('invitations.until', { date: formatDate(created.expires_at) })}
            </p>
          </div>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={make.isPending}
            onClick={() => make.mutate()}
          >
            {created ? t('invitations.again') : t('invitations.make')}
          </button>
        </div>
        <h2>{t('invitations.list')}</h2>
        {list.isError && problem(list.error) === t('invitations.error.noGroup') ? (
          <Alert kind="error">{problem(list.error)}</Alert>
        ) : (
          <QueryBoundary query={list}>
            {(data) =>
              data.items.length === 0 ? (
                <p className="muted">{t('invitations.none')}</p>
              ) : (
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id} data-testid={`invitation-${row.id}`}>
                      <span id={`invitation-text-${row.id}`}>
                        {t('invitations.row', {
                          made: formatDate(row.created_at),
                          until: formatDate(row.expires_at),
                        })}
                      </span>{' '}
                      <button
                        type="button"
                        className="btn btn-quiet"
                        aria-describedby={`invitation-text-${row.id}`}
                        disabled={end.isPending}
                        onClick={() => end.mutate(row.id)}
                      >
                        {t('invitations.revoke')}
                      </button>
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryBoundary>
        )}
      </div>
    </div>
  )
}
