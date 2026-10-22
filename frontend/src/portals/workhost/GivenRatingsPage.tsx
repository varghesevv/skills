import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { GIVEN_PAGE_SIZE, listGivenRatings } from '../../api/workhost'
import { t } from '../../i18n'
import { portalPath } from '../config'
import { term } from '../../terminology/terms'
import { formatDate } from '../../shared/dates'
import { Pager, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

export const GIVEN_KEY = ['host', 'given'] as const

export default function GivenRatingsPage() {
  usePageTitle(t('given.title'))
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: [...GIVEN_KEY, page],
    queryFn: () => listGivenRatings(page),
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <h1>{t('given.title')}</h1>
      <p className="lead">{t('given.lead')}</p>
      <QueryBoundary query={query}>
        {(data) =>
          data.total === 0 ? (
            <p className="muted">{t('given.empty')}</p>
          ) : (
            <>
              <ul className="stack plain-list">
                {data.items.map((item) => (
                  <li key={item.id} className="card">
                    <h2>
                      <Link
                        to={portalPath('workhost', term('freelancers_path'), item.freelancer_id)}
                      >
                        {item.freelancer_name ?? t('search.noName')}
                      </Link>
                    </h2>
                    <p className="rating-score">{t('ratings.score', { rating: item.rating })}</p>
                    <p>{item.comment ?? <span className="muted">{t('ratings.noComment')}</span>}</p>
                    <p className="muted">
                      {formatDate(item.rated_on)}
                      {item.updated_at &&
                        ` · ${t('given.updated', { date: formatDate(item.updated_at) })}`}
                    </p>
                  </li>
                ))}
              </ul>
              <Pager
                page={data.page}
                pageSize={GIVEN_PAGE_SIZE}
                total={data.total}
                onChange={setPage}
              />
            </>
          )
        }
      </QueryBoundary>
    </>
  )
}
