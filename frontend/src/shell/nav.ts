import type { PersonMe, PersonStatus } from '../api/types'
import { t, type StringKey } from '../i18n'
import { leadsOwnGroup } from '../pages/person/leads'
import {
  ADMIN_GROUPS,
  ADMIN_REPORTS,
  LEADER_APPLICANTS,
  LEADER_FLAGGED,
  LEADER_GROUP,
  LEADER_INVITATIONS,
  LEADER_MEMBERS,
  LEADER_REVOKED,
  OWNER_CHURCHES,
  OWNER_HANDOVER,
  OWNER_LABELS,
  OWNER_VIEWS,
  PERSON_AVAILABILITY,
  PERSON_MOVES,
  PERSON_PROFILE,
  PERSON_RATINGS,
  PERSON_RATINGS_GIVEN,
  PERSON_SEARCH,
  PERSON_SKILLS,
} from '../portals/config'

// docs/design-system.md, section 2.2: the one place that decides what each status sees in the
// top bar. A higher status includes the lower ones.

export type NavLinkItem = { to: string; label: string }
export type NavGroup = {
  id: 'find' | 'services' | 'church' | 'admin' | 'owner'
  label: string
  /** Shown as plain links in the bar (the everyday ones) rather than behind a button. */
  inline: boolean
  links: NavLinkItem[]
}

const ORDER: PersonStatus[] = ['searcher', 'provider', 'verifier', 'admin', 'owner']

/** Is the person's status this one or higher? A revoked or pending person is below all of them. */
export function atLeast(person: Pick<PersonMe, 'status'>, status: PersonStatus): boolean {
  const have = ORDER.indexOf(person.status)
  return have >= 0 && have >= ORDER.indexOf(status)
}

function link(to: string, label: StringKey): NavLinkItem {
  return { to, label: t(label) }
}

export function navFor(person: PersonMe): NavGroup[] {
  const groups: NavGroup[] = []
  if (atLeast(person, 'searcher')) {
    groups.push({
      id: 'find',
      label: t('member.nav.label'),
      inline: true,
      links: [link(PERSON_SEARCH, 'nav.search'), link(PERSON_RATINGS_GIVEN, 'nav.given')],
    })
  }
  if (atLeast(person, 'provider')) {
    groups.push({
      id: 'services',
      label: t('provider.nav.label'),
      inline: false,
      links: [
        link(PERSON_PROFILE, 'nav.profile'),
        link(PERSON_SKILLS, 'nav.labels'),
        link(PERSON_AVAILABILITY, 'nav.availability'),
        link(PERSON_RATINGS, 'nav.ratings'),
      ],
    })
  }
  if (atLeast(person, 'verifier')) {
    const church: NavLinkItem[] = [
      link(LEADER_APPLICANTS, 'leader.nav.applicants'),
      link(LEADER_MEMBERS, 'leader.nav.members'),
      link(LEADER_GROUP, 'leader.nav.group'),
    ]
    if (leadsOwnGroup(person)) church.push(link(LEADER_INVITATIONS, 'invitations.nav'))
    church.push(
      link(PERSON_MOVES, 'leader.nav.moves'),
      link(LEADER_FLAGGED, 'leader.nav.flagged'),
      link(LEADER_REVOKED, 'leader.nav.revoked'),
    )
    groups.push({ id: 'church', label: t('leader.nav.label'), inline: false, links: church })
  }
  if (atLeast(person, 'admin')) {
    groups.push({
      id: 'admin',
      label: t('nav.admin'),
      inline: false,
      links: [
        link(ADMIN_GROUPS, 'admin.nav.groups'),
        link(ADMIN_REPORTS, 'nav.reports'),
        link(OWNER_HANDOVER, 'handover.nav'),
      ],
    })
  }
  if (person.status === 'owner') {
    groups.push({
      id: 'owner',
      label: t('nav.owner'),
      inline: false,
      links: [
        link(OWNER_VIEWS, 'owner.nav.views'),
        link(OWNER_LABELS, 'nav.adminLabels'),
        link(OWNER_CHURCHES, 'owner.nav.churches'),
      ],
    })
  }
  return groups
}
