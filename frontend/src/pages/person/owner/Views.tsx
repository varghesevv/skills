import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { fetchContactViews, LEADER_PAGE_SIZE } from '../../../api/person'
import type { IdName } from '../../../api/types'
import { t } from '../../../i18n'
import { formatDateTime } from '../../../shared/dates'
import { Pager, QueryBoundary } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

type Filter = { viewer?: IdName; person?: IdName }

/** The log of phone number views, for the OWNER: who looked at whose number, when, newest first.
 *  The number is never in it. A name can be clicked to narrow the log to that viewer or person. */
export default function Views() {
  usePageTitle(t('views.title'))
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<Filter>({})
  const list = useQuery({
    queryKey: ['contact-views', page, filter.viewer?.id ?? '', filter.person?.id ?? ''],
    queryFn: () =>
      fetchContactViews(page, { viewerId: filter.viewer?.id, personId: filter.person?.id }),
  })
  const narrow = (next: Filter) => {
    setFilter(next)
    setPage(1)
  }
  // A closed account has no name any more; say so instead of showing nothing.
  const word = (who: IdName) => who.name || t('views.noName')
  return (
    <div className="container">
      <div className="card">
        <h1>{t('views.title')}</h1>
        <p className="lead">{t('views.lead')}</p>
        {(filter.viewer || filter.person) && (
          <p>
            {filter.viewer && <>{t('views.filter.viewer', { name: word(filter.viewer) })} </>}
            {filter.person && <>{t('views.filter.person', { name: word(filter.person) })} </>}
            <button type="button" className="btn btn-quiet" onClick={() => narrow({})}>
              {t('views.clear')}
            </button>
          </p>
        )}
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('views.none')}</p>
            ) : (
              <>
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id}>
                      {t('views.row', { viewer: word(row.viewer), person: word(row.person) })}
                      {' · '}
                      <time dateTime={row.viewed_at}>{formatDateTime(row.viewed_at)}</time>{' '}
                      {!filter.viewer && (
                        <button
                          type="button"
                          className="btn btn-quiet"
                          onClick={() => narrow({ ...filter, viewer: row.viewer })}
                        >
                          {t('views.only.viewer', { name: word(row.viewer) })}
                        </button>
                      )}{' '}
                      {!filter.person && (
                        <button
                          type="button"
                          className="btn btn-quiet"
                          onClick={() => narrow({ ...filter, person: row.person })}
                        >
                          {t('views.only.person', { name: word(row.person) })}
                        </button>
                      )}
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
