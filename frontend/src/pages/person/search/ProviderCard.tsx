import { Link } from 'react-router-dom'

import type { SearchResult } from '../../../api/types'
import { t } from '../../../i18n'
import { PERSON_PROVIDERS } from '../../../portals/config'
import { Badge } from '../../../shared/ui'
import { formatRate } from './format'
import RevealMobile from './RevealMobile'

const MAX_PILLS = 4

/** How many of the searched skills the provider has, compared without regard to case; null when
 *  no skill is searched. Worked out here from the filter and the result: the API sends no score
 *  (docs/design-system.md, section 2.4). */
export function skillMatch(
  item: Pick<SearchResult, 'skills'>,
  searched: string[],
): { have: number; of: number } | null {
  if (searched.length === 0) return null
  const has = new Set(item.skills.map((skill) => skill.name.toLowerCase()))
  const have = new Set(searched.map((name) => name.toLowerCase()).filter((name) => has.has(name)))
  const of = new Set(searched.map((name) => name.toLowerCase())).size
  return { have: have.size, of }
}

function ShieldIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3l8 3v6c0 4.5-3.2 8.2-8 9-4.8-.8-8-4.5-8-9V6l8-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  )
}

/** One provider in the results (docs/design-system.md, sections 2.4 and 3.2). The name is a real
 *  link and covers the whole card; Reveal stays above it. */
export default function ProviderCard({
  item,
  search,
  searchedSkills,
  matchAny,
  own,
}: {
  item: SearchResult
  search: string
  searchedSkills: string[]
  /** The match is shown only for "any": with "all" every result matches in full. */
  matchAny: boolean
  own: boolean
}) {
  const name = item.full_name ?? t('search.noName')
  const match = matchAny ? skillMatch(item, searchedSkills) : null
  const extra = item.skills.length - MAX_PILLS
  return (
    <li className="card pcard">
      <h2 className="pcard-name">
        <span className="pcard-initials" aria-hidden="true">
          {name.slice(0, 1).toUpperCase()}
        </span>
        <Link className="pcard-link" to={`${PERSON_PROVIDERS}/${item.id}`} state={{ search }}>
          {name}
        </Link>
      </h2>
      <p className="pcard-rate">
        <strong>{formatRate(item.rate_per_hour, item.rate_currency)}</strong>{' '}
        {item.is_rate_negotiable && <Badge tone="good">{t('search.negotiableTag')}</Badge>}
      </p>
      <p className="pcard-rating">
        {item.average_rating === null
          ? t('search.noRatings')
          : t('search.average', {
              average: item.average_rating.toFixed(1),
              count: item.rating_count,
            })}
      </p>
      <p className="pcard-trust">
        <ShieldIcon />
        <span>
          {t('search.trustLine', { church: item.church.name, group: item.home_group.name })}
        </span>
      </p>
      {match && <p className="pcard-match">{t('search.skillMatch.of', match)}</p>}
      <ul className="pills plain-list" aria-label={t('search.skillsLabel')}>
        {item.skills.slice(0, MAX_PILLS).map((skill) => (
          <li key={skill.name} className="pill">
            {skill.name}
            {skill.level && <span> · {skill.level}</span>}
          </li>
        ))}
        {extra > 0 && (
          <li className="pill pill-more">{t('search.moreSkills', { count: extra })}</li>
        )}
      </ul>
      <p className="muted pcard-small">
        {[item.nationality, ...item.languages].filter(Boolean).join(' · ')}
      </p>
      {!own && (
        <div className="pcard-foot">
          <RevealMobile
            freelancerId={item.id}
            freelancerName={name}
            source="search"
            searchedSkills={searchedSkills}
          />
        </div>
      )}
    </li>
  )
}
