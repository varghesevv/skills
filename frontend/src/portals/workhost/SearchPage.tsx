import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { listLabels } from '../../api/freelancer'
import type { SearchResult } from '../../api/types'
import { SEARCH_PAGE_SIZE, listOrganisations, searchFreelancers } from '../../api/workhost'
import { t } from '../../i18n'
import { Badge, Pager, QueryBoundary, SelectField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import FilterForm, { SORT_OPTIONS } from './FilterForm'
import { formatRate } from './format'
import {
  activeFilterCount,
  apiQuery,
  pageFromParams,
  paramsFromValues,
  valuesFromParams,
  type FilterValues,
  type SortKey,
} from './searchParams'

function ResultCard({
  item,
  search,
  portal,
}: {
  item: SearchResult
  search: string
  portal: Portal
}) {
  return (
    <li className="card result">
      <h2>
        <Link to={`/${portal}/freelancers/${item.id}`} state={{ search }}>
          {item.full_name ?? t('search.noName')}
        </Link>
      </h2>
      <p className="result-rate">
        <strong>{formatRate(item.rate_per_hour, item.rate_currency)}</strong>{' '}
        {item.is_rate_negotiable && <Badge tone="good">{t('search.negotiableTag')}</Badge>}
      </p>
      <p>
        {item.average_rating === null
          ? t('search.noRatings')
          : t('search.average', {
              average: item.average_rating.toFixed(1),
              count: item.rating_count,
            })}
        {item.vouch_count > 0 && <> · {t('search.vouches', { count: item.vouch_count })}</>}
      </p>
      <ul className="chips plain-list">
        {item.skills.map((skill) => (
          <li key={skill.name} className="chip">
            {skill.name}
            {skill.level && <span className="muted"> · {skill.level}</span>}
          </li>
        ))}
      </ul>
      <p className="muted">{[item.nationality, ...item.languages].filter(Boolean).join(' · ')}</p>
    </li>
  )
}

export type Portal = 'workhost' | 'organisation'

/** The freelancer search, shared by work hosts and organisations (who search to find people to vouch for). */
export default function SearchPage({ portal }: { portal: Portal }) {
  usePageTitle(t('search.title'))
  const [params, setParams] = useSearchParams()
  const [panelOpen, setPanelOpen] = useState(false)
  const filterButton = useRef<HTMLButtonElement>(null)

  const applied = valuesFromParams(params)
  const page = pageFromParams(params)
  const filterKey = paramsFromValues(applied).toString()
  const paramsKey = params.toString()

  const labels = useQuery({ queryKey: ['labels'], queryFn: listLabels })
  // The organisation filter is optional: if the list cannot be loaded the rest still works.
  const organisations = useQuery({ queryKey: ['organisations'], queryFn: listOrganisations })
  const results = useQuery({
    queryKey: ['search', paramsKey],
    queryFn: () => searchFreelancers(apiQuery(params, page, SEARCH_PAGE_SIZE)),
    placeholderData: (previous) => previous,
  })

  useEffect(() => {
    if (!panelOpen) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setPanelOpen(false)
        filterButton.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [panelOpen])

  function apply(values: FilterValues) {
    setParams(paramsFromValues(values))
    setPanelOpen(false)
  }

  function changeSort(sort: string) {
    apply({ ...applied, sort: sort as SortKey })
  }

  function goToPage(next: number) {
    const updated = new URLSearchParams(params)
    updated.set('page', String(next))
    setParams(updated)
  }

  const count = activeFilterCount(applied)

  return (
    <>
      <h1>{t('search.title')}</h1>
      <p className="lead">{t('search.lead')}</p>

      <div className="search-layout">
        <aside
          id="filter-panel"
          className="filter-panel"
          data-open={panelOpen}
          aria-label={t('search.filters')}
        >
          <div className="filter-head">
            <h2>{t('search.filters')}</h2>
            <button
              type="button"
              className="icon-btn filter-close"
              onClick={() => setPanelOpen(false)}
            >
              <span aria-hidden="true">✕</span>
              <span className="sr-only">{t('search.closeFilters')}</span>
            </button>
          </div>
          <QueryBoundary query={labels}>
            {(available) => (
              <FilterForm
                key={`${filterKey}-${organisations.data?.length ?? 0}`}
                labels={available}
                organisations={organisations.data ?? []}
                initial={applied}
                onApply={apply}
              />
            )}
          </QueryBoundary>
        </aside>
        {panelOpen && (
          <div className="backdrop" aria-hidden="true" onClick={() => setPanelOpen(false)} />
        )}

        <section aria-label={t('search.title')}>
          <div className="toolbar">
            <button
              ref={filterButton}
              type="button"
              className="btn btn-quiet filter-toggle"
              aria-expanded={panelOpen}
              aria-controls="filter-panel"
              onClick={() => setPanelOpen((current) => !current)}
            >
              {count > 0 ? t('search.filtersActive', { count }) : t('search.filters')}
            </button>
            <SelectField
              className="sort-field"
              label={t('search.sort')}
              name="sort"
              value={applied.sort}
              onChange={changeSort}
              options={SORT_OPTIONS}
            />
          </div>
          <QueryBoundary query={results}>
            {(data) =>
              data.total === 0 ? (
                <p className="muted">{t('search.none')}</p>
              ) : (
                <>
                  <p role="status">{t('search.results', { count: data.total })}</p>
                  <ul className="result-grid plain-list">
                    {data.items.map((item) => (
                      <ResultCard key={item.id} item={item} search={paramsKey} portal={portal} />
                    ))}
                  </ul>
                  <Pager
                    page={data.page}
                    pageSize={SEARCH_PAGE_SIZE}
                    total={data.total}
                    onChange={goToPage}
                  />
                </>
              )
            }
          </QueryBoundary>
        </section>
      </div>
    </>
  )
}
