import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchFlagged, LEADER_PAGE_SIZE } from '../../../api/person'
import { t } from '../../../i18n'
import { LEADER_PERSON } from '../../../portals/config'
import { Pager, QueryBoundary } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

/** People whose status was set by someone since revoked. They keep their access; a leader
 *  confirms each one from their own page. No numbers in the list. */
export default function Flagged() {
  usePageTitle(t('leader.flagged.title'))
  const [page, setPage] = useState(1)
  const list = useQuery({ queryKey: ['flagged', page], queryFn: () => fetchFlagged(page) })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('leader.flagged.title')}</h1>
        <p className="lead">{t('leader.flagged.lead')}</p>
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('leader.flagged.none')}</p>
            ) : (
              <>
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id}>
                      <Link to={`${LEADER_PERSON}/${row.id}`}>{row.full_name}</Link>
                      {' · '}
                      {t(`status.${row.status}`)}
                      {row.home_group && <> · {row.home_group.name}</>}
                      {' · '}
                      {t('leader.flagged.row', {
                        by: row.status_set_by?.name ?? t('leader.history.noone'),
                      })}
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
