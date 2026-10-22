import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { RATINGS_PAGE_SIZE, listRatings } from '../../api/freelancer'
import { useUser } from '../../auth/AuthContext'
import { t } from '../../i18n'
import { formatDate } from '../../shared/dates'
import { Pager, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

export default function RatingsPage() {
  usePageTitle(t('ratings.title'))
  const user = useUser()
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['freelancer', 'ratings', user.id, page],
    queryFn: () => listRatings(user.id, page),
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <h1>{t('ratings.title')}</h1>
      <p className="lead">{t('ratings.lead')}</p>
      <QueryBoundary query={query}>
        {(data) =>
          data.total === 0 ? (
            <p className="muted">{t('ratings.empty')}</p>
          ) : (
            <>
              <p>{t('ratings.count', { count: data.total })}</p>
              <ul className="stack plain-list">
                {data.items.map((item, index) => (
                  <li key={`${item.rated_on}-${index}`} className="card">
                    <p className="rating-score">{t('ratings.score', { rating: item.rating })}</p>
                    <p>{item.comment ?? <span className="muted">{t('ratings.noComment')}</span>}</p>
                    <p className="muted">{formatDate(item.rated_on)}</p>
                  </li>
                ))}
              </ul>
              <Pager
                page={data.page}
                pageSize={RATINGS_PAGE_SIZE}
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
