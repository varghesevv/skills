import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { fetchPersonDetail } from '../../../api/person'
import type { HistoryEntry, PersonDetail as Detail } from '../../../api/types'
import { ApiError } from '../../../api/http'
import { t } from '../../../i18n'
import { LEADER_MEMBERS } from '../../../portals/config'
import { formatDate, formatDateTime } from '../../../shared/dates'
import { errorMessage } from '../../../shared/errors'
import { Alert } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'
import AdmitControls, { type Outcome } from './AdmitControls'

const KINDS = [
  'signup',
  'admit',
  'appoint',
  'step-down',
  'revoke',
  'reinstate',
  'reconfirm',
  'handover',
  'operator',
] as const

function historyText(entry: HistoryEntry): string {
  const kind = (KINDS as readonly string[]).includes(entry.kind)
    ? t(`leader.history.${entry.kind as (typeof KINDS)[number]}`)
    : entry.kind
  return t('leader.history', {
    kind,
    from: entry.from_status ? t(`status.${entry.from_status as 'pending'}`) : '—',
    to: t(`status.${entry.to_status as 'pending'}`),
    by: entry.changed_by?.name || t('leader.history.noone'),
  })
}

type Load =
  { state: 'loading' } | { state: 'error'; error: unknown } | { state: 'ok'; data: Detail }

/** Only digits, a leading plus and spaces go into the link. */
const telNumber = (number: string) => number.replace(/[^\d+ ]/g, '')

/** One person in the leader's scope: the number, the history and the chain of trust.
 *
 *  Every time this page asks the server, the view is recorded, so it asks once. The answer is kept
 *  in this page's own state, not in the query cache: the number is gone when the page is left.
 *  After an admission the page updates itself from the answer instead of asking again. */
export default function PersonDetail() {
  usePageTitle(t('leader.person.title'))
  const { id = '' } = useParams()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [done, setDone] = useState<string | null>(null)
  const [declined, setDeclined] = useState(false)

  useEffect(() => {
    let current = true
    setLoad({ state: 'loading' })
    fetchPersonDetail(id).then(
      (data) => current && setLoad({ state: 'ok', data }),
      (error: unknown) => current && setLoad({ state: 'error', error }),
    )
    return () => {
      current = false
    }
  }, [id, attempt])

  const onDone = useCallback((message: string, outcome: Outcome) => {
    setDone(message)
    if (outcome === 'declined') {
      setDeclined(true)
    } else {
      setLoad((previous) =>
        previous.state === 'ok'
          ? {
              state: 'ok',
              data: {
                ...previous.data,
                status: outcome.status,
                requested_status: outcome.requested_status,
              },
            }
          : previous,
      )
    }
  }, [])

  return (
    <div className="container">
      <div className="card">
        {load.state === 'loading' && (
          <p role="status" className="muted">
            {t('loading')}
          </p>
        )}
        {load.state === 'error' && (
          <>
            <h1>{t('leader.person.title')}</h1>
            <Alert kind="error">
              <p>{errorMessage(load.error)}</p>
              {!(load.error instanceof ApiError && load.error.status === 404) && (
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => setAttempt((n) => n + 1)}
                >
                  {t('common.retry')}
                </button>
              )}
            </Alert>
          </>
        )}
        {load.state === 'ok' && declined && (
          <>
            <h1>{t('leader.person.title')}</h1>
            {done && <Alert kind="success">{done}</Alert>}
          </>
        )}
        {load.state === 'ok' && !declined && (
          <PersonView data={load.data} done={done} onDone={onDone} />
        )}
        <p>
          <Link to={LEADER_MEMBERS}>{t('leader.person.back')}</Link>
        </p>
      </div>
    </div>
  )
}

function PersonView({
  data,
  done,
  onDone,
}: {
  data: Detail
  done: string | null
  onDone: (message: string, outcome: Outcome) => void
}) {
  return (
    <>
      <h1>{data.full_name}</h1>
      {done && <Alert kind="success">{done}</Alert>}
      <dl className="facts">
        <dt>{t('leader.person.status')}</dt>
        <dd>{t(`status.${data.status}`)}</dd>
        <dt>{t('leader.person.church')}</dt>
        <dd>{data.church.name}</dd>
        <dt>{t('leader.person.group')}</dt>
        <dd>{data.home_group?.name ?? '—'}</dd>
        {data.requested_status && (
          <>
            <dt>{t('leader.person.applyingFor')}</dt>
            <dd>{t(`vouch.page.goal.${data.requested_status}`)}</dd>
          </>
        )}
        <dt>{t('leader.person.mobile')}</dt>
        <dd>
          <a href={`tel:${telNumber(data.mobile_number)}`}>{data.mobile_number}</a>
        </dd>
        <dt>{t('leader.person.setBy')}</dt>
        <dd>{data.status_set_by?.name ?? '—'}</dd>
        <dt>{t('leader.person.applied')}</dt>
        <dd>{formatDate(data.applied_at)}</dd>
      </dl>
      <p className="hint">{t('leader.person.numberNote')}</p>

      {data.status === 'pending' && (
        <AdmitControls
          id={data.id}
          name={data.full_name}
          liveVouches={data.vouches.filter((v) => v.live).length}
          onDone={onDone}
        />
      )}

      <h2>{t('leader.person.vouches')}</h2>
      {data.vouches.length === 0 ? (
        <p className="muted">{t('leader.person.none')}</p>
      ) : (
        <ul className="plain-list">
          {data.vouches.map((voucher, index) => (
            <li key={index}>
              {t('vouch.received.from', {
                name: voucher.name,
                church: voucher.church_name,
              })}
              {!voucher.live && <> · {t('vouch.received.notCounting')}</>}
            </li>
          ))}
        </ul>
      )}

      <h2>{t('leader.person.history')}</h2>
      <ul className="plain-list">
        {data.history.map((entry, index) => (
          <li key={index}>
            {historyText(entry)} · <time dateTime={entry.at}>{formatDateTime(entry.at)}</time>
          </li>
        ))}
      </ul>

      <h2>{t('leader.person.chain')}</h2>
      <p className="hint">{t('leader.person.chainText')}</p>
      {data.chain_of_trust.length === 0 ? (
        <p className="muted">{t('leader.person.none')}</p>
      ) : (
        <ol className="plain-list">
          {data.chain_of_trust.map((link) => (
            <li key={link.id}>
              {link.full_name || '—'} · {t(`status.${link.status}`)}
            </li>
          ))}
        </ol>
      )}
    </>
  )
}
