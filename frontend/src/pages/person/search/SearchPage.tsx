import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import { listLabels } from '../../../api/freelancer'
import { fetchChurches, fetchHomeGroups } from '../../../api/person'
import { SEARCH_PAGE_SIZE, searchProviders } from '../../../api/providers'
import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { useDesktop } from '../../../shell/useWide'
import { Pager, QueryBoundary, SelectField, TextField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'
import { activeChips, clearedFilters } from './activeFilters'
import FilterForm, { SORT_OPTIONS } from './FilterForm'
import ProviderCard from './ProviderCard'
import {
  activeFilterCount,
  apiQuery,
  pageFromParams,
  paramsFromValues,
  valuesFromParams,
  type FilterValues,
  type SortKey,
} from './searchParams'

/** Cards of the size of the real ones, so nothing moves when the results arrive. */
function ResultsSkeleton() {
  return (
    <ul className="result-grid plain-list" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5].map((n) => (
        <li key={n} className="card pcard pcard-skeleton" />
      ))}
    </ul>
  )
}

/** The provider search: for a SEARCHER and everyone above, over every church. */
export default function SearchPage() {
  const me = usePerson()
  const [params, setParams] = useSearchParams()
  const [panelOpen, setPanelOpen] = useState(false)
  const live = useDesktop() // from 1024px the filters apply as they change
  const filterButton = useRef<HTMLButtonElement>(null)

  const applied = valuesFromParams(params)
  const page = pageFromParams(params)
  const filterKey = paramsFromValues(applied).toString()
  const paramsKey = params.toString()

  const labels = useQuery({ queryKey: ['labels'], queryFn: listLabels })
  // The church filter is optional: if the lists cannot be loaded the rest still works.
  const churches = useQuery({ queryKey: ['churches'], queryFn: fetchChurches })
  const groups = useQuery({
    queryKey: ['church-groups', applied.churchId],
    queryFn: () => fetchHomeGroups(applied.churchId),
    enabled: applied.churchId !== '',
  })
  const results = useQuery({
    queryKey: ['search', paramsKey],
    queryFn: () => searchProviders(apiQuery(params, page, SEARCH_PAGE_SIZE)),
    placeholderData: (previous) => previous,
  })

  // The number of matches is in the page title, so a tab or history entry says what it holds.
  usePageTitle(
    results.data ? t('search.results', { count: results.data.total }) : t('search.title'),
  )

  const [nameText, setNameText] = useState(applied.name)
  useEffect(() => {
    setNameText(applied.name)
  }, [applied.name])

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

  function searchByName(event: FormEvent) {
    event.preventDefault()
    apply({ ...applied, name: nameText.trim() })
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
  const chips = activeChips(applied, {
    churches: churches.data?.items ?? [],
    groups: groups.data?.items ?? [],
  })

  return (
    <div className="container">
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
                key={`${live ? 'live' : filterKey}-${churches.data?.items.length ?? 0}`}
                labels={available}
                churches={churches.data?.items ?? []}
                initial={applied}
                onApply={apply}
                live={live}
              />
            )}
          </QueryBoundary>
        </aside>
        {panelOpen && (
          <div className="backdrop" aria-hidden="true" onClick={() => setPanelOpen(false)} />
        )}

        <section aria-label={t('search.title')}>
          <form className="name-search" role="search" onSubmit={searchByName} noValidate>
            <TextField
              label={t('search.name')}
              name="name"
              autoComplete="off"
              maxLength={100}
              value={nameText}
              onChange={setNameText}
            />
            <button type="submit" className="btn btn-primary">
              {t('search.nameGo')}
            </button>
          </form>
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
          {chips.length > 0 && (
            <ul className="active-filters plain-list" aria-label={t('search.chips')}>
              {chips.map((chip) => (
                <li key={chip.key}>
                  <button
                    type="button"
                    className="chip-remove"
                    aria-label={t('search.chip.remove', { label: chip.label })}
                    onClick={() => apply(chip.without(applied))}
                  >
                    {chip.label} <span aria-hidden="true">✕</span>
                  </button>
                </li>
              ))}
              <li>
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => apply(clearedFilters(applied))}
                >
                  {t('search.clearAll')}
                </button>
              </li>
            </ul>
          )}
          <QueryBoundary query={results} pending={<ResultsSkeleton />}>
            {(data) =>
              data.total === 0 ? (
                <div role="status">
                  <p className="muted">{t('search.none')}</p>
                  {chips.length > 0 && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => apply(clearedFilters(applied))}
                    >
                      {t('search.clearAll')}
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <p role="status">{t('search.results', { count: data.total })}</p>
                  <ul
                    className={`result-grid plain-list${results.isFetching ? ' is-stale' : ''}`}
                    aria-busy={results.isFetching}
                  >
                    {data.items.map((item) => (
                      <ProviderCard
                        key={item.id}
                        item={item}
                        search={paramsKey}
                        searchedSkills={applied.skills}
                        matchAny={applied.skillMatch === 'any'}
                        own={item.id === me.id}
                      />
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
    </div>
  )
}
