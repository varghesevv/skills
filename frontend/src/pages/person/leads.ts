import type { PersonMe } from '../../api/types'

/** Does this person lead the group they belong to? `/me` carries only the leader's name, so the
 *  names are compared; the server decides in the end, and a wrong guess only shows a choice the
 *  server then refuses in words. */
export function leadsOwnGroup(person: PersonMe): boolean {
  return (
    person.home_group !== null &&
    ['verifier', 'admin', 'owner'].includes(person.status) &&
    person.leader?.name === person.full_name
  )
}
