import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchRevoked, LEADER_PAGE_SIZE } from '../../../api/person'
import { t } from '../../../i18n'
import { LEADER_PERSON } from '../../../portals/config'
import { formatDate } from '../../../shared/dates'
import { Pager, QueryBoundary } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

/** The revoked people of the leader's scope, with the group they were removed from. A revoked
 *  person is brought back from their own page. No numbers in the list. */
export default function Revoked() {
  usePageTitle(t('leader.revoked.title'))
  const [page, setPage] = useState(1)
  const list = useQuery({ queryKey: ['revoked', page], queryFn: () => fetchRevoked(page) })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('leader.revoked.title')}</h1>
        <p className="lead">{t('leader.revoked.lead')}</p>
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('leader.revoked.none')}</p>
            ) : (
              <>
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id}>
                      <Link to={`${LEADER_PERSON}/${row.id}`}>{row.full_name}</Link>
                      {' · '}
                      {t('leader.revoked.row', {
                        group: row.removed_from?.name ?? '—',
                        by: row.revoked_by?.name ?? t('leader.history.noone'),
                      })}
                      {row.revoked_at && <> · {formatDate(row.revoked_at)}</>}
                    </li>
                  ))}
                </ul>
                <Pager
                  page={page}
                  pageSize={LEADER_PAGE_SIZE}
                  total={data.total}
                  onChange={setPage}
                />
              </>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}
