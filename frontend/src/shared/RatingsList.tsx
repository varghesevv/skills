import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { RATINGS_PAGE_SIZE, listRatings } from '../api/freelancer'
import { t } from '../i18n'
import { formatDate } from './dates'
import { Pager, QueryBoundary } from './ui'

/** The ratings a freelancer received, newest first, without who gave them. */
export default function RatingsList({ freelancerId }: { freelancerId: string }) {
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['ratings', freelancerId, page],
    queryFn: () => listRatings(freelancerId, page),
    placeholderData: (previous) => previous,
  })

  return (
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
  )
}
