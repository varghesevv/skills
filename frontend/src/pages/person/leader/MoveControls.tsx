import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../../../api/http'
import { fetchHomeGroups, movePerson } from '../../../api/person'
import type { PersonDetail } from '../../../api/types'
import { t } from '../../../i18n'
import { errorMessage } from '../../../shared/errors'
import { Alert, SelectField } from '../../../shared/ui'
import type { Change } from './StatusControls'

/** An ADMIN or the OWNER move an admitted member who leads nothing to another open group of the
 *  church, without the agreements a move by request needs. */
export default function MoveControls({
  person,
  onDone,
}: {
  person: PersonDetail
  onDone: (message: string, change: Change) => void
}) {
  const queryClient = useQueryClient()
  const [group, setGroup] = useState('')
  const groups = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
  })
  const move = useMutation({
    mutationFn: () => movePerson(person.id, group),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['members'] })
      setGroup('')
      onDone(t('admin.move.done', { name: person.full_name, group: result.home_group.name }), {
        home_group: result.home_group,
      })
    },
  })
  const others = (groups.data?.items ?? []).filter((g) => g.id !== person.home_group?.id)
  if (others.length === 0) return null
  const failure = move.error
  const message =
    failure instanceof ApiError && failure.code === 'leads_a_group'
      ? t('admin.move.leads', { name: person.full_name })
      : failure
        ? errorMessage(failure)
        : null
  return (
    <form
      className="form-grid"
      aria-label={t('admin.move.title', { name: person.full_name })}
      onSubmit={(event) => {
        event.preventDefault()
        if (group) move.mutate()
      }}
    >
      <h2 className="span-2">{t('admin.move.title', { name: person.full_name })}</h2>
      {message && (
        <Alert kind="error" focus>
          {message}
        </Alert>
      )}
      <SelectField
        label={t('admin.move.to')}
        name="move-to"
        value={group}
        onChange={setGroup}
        options={[
          { value: '', label: t('admin.move.choose') },
          ...others.map((g) => ({ value: g.id, label: g.name })),
        ]}
      />
      <div className="form-actions span-2">
        <button type="submit" className="btn btn-primary" disabled={move.isPending || !group}>
          {t('admin.move.submit', { name: person.full_name })}
        </button>
      </div>
    </form>
  )
}
