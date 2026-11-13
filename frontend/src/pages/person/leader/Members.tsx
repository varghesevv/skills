import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchMembers, LEADER_PAGE_SIZE } from '../../../api/person'
import { t } from '../../../i18n'
import { LEADER_PERSON } from '../../../portals/config'
import { Badge, Pager, QueryBoundary, SelectField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

const FILTERS = ['searcher', 'provider', 'verifier', 'admin', 'owner'] as const
type Filter = (typeof FILTERS)[number]

/** The admitted people in the leader's scope, by name; no numbers in the list. */
export default function Members() {
  usePageTitle(t('leader.members.title'))
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<Filter | ''>('')
  const list = useQuery({
    queryKey: ['members', page, status],
    queryFn: () => fetchMembers(page, status || undefined),
  })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('leader.members.title')}</h1>
        <SelectField
          label={t('leader.members.filter')}
          name="status"
          value={status}
          onChange={(value) => {
            setStatus(value as Filter | '')
            setPage(1)
          }}
          options={[
            { value: '', label: t('leader.members.all') },
            ...FILTERS.map((value) => ({ value, label: t(`status.${value}`) })),
          ]}
        />
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('leader.members.none')}</p>
            ) : (
              <>
                <ul className="plain-list">
                  {data.items.map((row) => (
                    <li key={row.id}>
                      <Link to={`${LEADER_PERSON}/${row.id}`}>{row.full_name}</Link>
                      {' · '}
                      {t(`status.${row.status}`)}
                      {row.home_group && <> · {row.home_group.name}</>}
                      {row.status_set_by && (
                        <> · {t('leader.members.admittedBy', { name: row.status_set_by.name })}</>
                      )}
                      {row.flagged_for_recheck && (
                        <>
                          {' '}
                          <Badge tone="warn">{t('leader.members.flagged')}</Badge>
                        </>
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
