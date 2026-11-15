import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { fetchVouchesReceived, fetchVouchLinkState, makeVouchLink } from '../../api/person'
import type { VouchLinkCreated } from '../../api/types'
import { t } from '../../i18n'
import { VOUCH_LINK_PREFIX } from '../../portals/config'
import { formatDate, formatDateTime } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary } from '../../shared/ui'

/** The address a person sends to people who know them. The token is the last part. */
export function vouchLinkUrl(token: string): string {
  return `${window.location.origin}${VOUCH_LINK_PREFIX}${token}`
}

/** For an applicant: make a link to share, and see the vouches received so far. */
export default function VouchShare() {
  return (
    <>
      <ShareLink />
      <Received />
    </>
  )
}

function ShareLink() {
  const queryClient = useQueryClient()
  const state = useQuery({ queryKey: ['vouch-link'], queryFn: fetchVouchLinkState })
  const [created, setCreated] = useState<VouchLinkCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const field = useRef<HTMLInputElement>(null)
  const make = useMutation({
    mutationFn: makeVouchLink,
    onSuccess: (link) => {
      setCreated(link)
      setCopied(false)
      void queryClient.invalidateQueries({ queryKey: ['vouch-link'] })
    },
  })
  const url = created ? vouchLinkUrl(created.token) : ''

  async function copy() {
    field.current?.select()
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // Without clipboard access the link stays selected, so the person can copy it by hand.
    }
  }

  async function share() {
    try {
      await navigator.share({ url })
    } catch {
      // The person closed the share sheet: nothing to do.
    }
  }

  return (
    <section className="card" aria-labelledby="vouch-share-title">
      <h2 id="vouch-share-title">{t('vouch.share.title')}</h2>
      <p>{t('vouch.share.text')}</p>
      <QueryBoundary query={state}>
        {(data) => (
          <>
            {!created && (
              <p className="hint">
                {data.active && data.expires_at
                  ? t('vouch.share.active', { date: formatDate(data.expires_at) })
                  : t('vouch.share.none')}
              </p>
            )}
            {make.isError && (
              <Alert kind="error" focus>
                {errorMessage(make.error)}
              </Alert>
            )}
            {created && (
              <div className="form-grid">
                <p className="span-2">{t('vouch.share.once')}</p>
                <label className="field span-2">
                  <span className="field-label">{t('vouch.share.label')}</span>
                  <input ref={field} readOnly value={url} onFocus={(e) => e.target.select()} />
                </label>
                <div className="form-actions span-2">
                  <button type="button" className="btn btn-primary" onClick={() => void copy()}>
                    {copied ? t('vouch.share.copied') : t('vouch.share.copy')}
                  </button>
                  {typeof navigator.share === 'function' && (
                    <button type="button" className="btn btn-quiet" onClick={() => void share()}>
                      {t('vouch.share.send')}
                    </button>
                  )}
                </div>
                <p className="hint span-2">
                  {t('vouch.share.active', { date: formatDate(created.expires_at) })}
                </p>
              </div>
            )}
            <button
              type="button"
              className="btn btn-quiet"
              disabled={make.isPending}
              onClick={() => make.mutate()}
            >
              {make.isPending
                ? t('vouch.share.working')
                : data.active || created
                  ? t('vouch.share.again')
                  : t('vouch.share.make')}
            </button>
          </>
        )}
      </QueryBoundary>
    </section>
  )
}

function Received() {
  const received = useQuery({
    queryKey: ['vouches-received'],
    queryFn: fetchVouchesReceived,
    refetchInterval: 60_000,
  })
  return (
    <section className="card" aria-labelledby="vouch-received-title">
      <h2 id="vouch-received-title">{t('vouch.received.title')}</h2>
      <QueryBoundary query={received}>
        {(data) =>
          data.items.length === 0 ? (
            <p className="muted">{t('vouch.received.none')}</p>
          ) : (
            <ul className="plain-list">
              {data.items.map((vouch) => (
                <li key={vouch.id}>
                  {t('vouch.received.from', {
                    name: vouch.voucher_name,
                    church: vouch.church_name,
                  })}
                  {' · '}
                  <time dateTime={vouch.created_at}>{formatDateTime(vouch.created_at)}</time>
                  {!vouch.live && <> · {t('vouch.received.notCounting')}</>}
                </li>
              ))}
            </ul>
          )
        }
      </QueryBoundary>
    </section>
  )
}
