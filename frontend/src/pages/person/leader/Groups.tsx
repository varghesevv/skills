import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../../../api/http'
import {
  fetchHomeGroups,
  fetchMembers,
  replaceLeader,
  type FormerLeaderStatus,
} from '../../../api/person'
import type { HomeGroupSummary } from '../../../api/types'
import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import { errorMessage } from '../../../shared/errors'
import { Alert, QueryBoundary, SelectField } from '../../../shared/ui'
import { usePageTitle } from '../../../shared/usePageTitle'

/** The words for a refused change of leader. The server's code decides. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'successor_not_member') return t('admin.error.notMember')
    if (error.code === 'invalid_choice') return t('admin.error.choice')
    if (error.code === 'status_not_allowed') return t('leader.error.notAllowed')
    if (error.code === 'state_changed') return t('leader.error.changed')
  }
  return errorMessage(error)
}

/** The open groups of the ADMIN's church (the OWNER's own church), each with a way to choose who
 *  leads it from now on. The old leader stays in the group, as a provider or a searcher, or keeps
 *  their status if they are an ADMIN or the OWNER handing on their own group. */
export default function Groups() {
  const person = usePerson()
  usePageTitle(t('admin.groups.title'))
  const [done, setDone] = useState<string | null>(null)
  const list = useQuery({
    queryKey: ['church-groups', person.church.id],
    queryFn: () => fetchHomeGroups(person.church.id),
  })
  return (
    <div className="container">
      <div className="card">
        <h1>{t('admin.groups.title')}</h1>
        <p className="lead">{t('admin.groups.lead')}</p>
        {done && (
          <Alert kind="success" focus>
            {done}
          </Alert>
        )}
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('admin.groups.none')}</p>
            ) : (
              <ul className="plain-list">
                {data.items.map((group) => (
                  <li key={group.id}>
                    <GroupRow group={group} onDone={setDone} />
                  </li>
                ))}
              </ul>
            )
          }
        </QueryBoundary>
      </div>
    </div>
  )
}

function GroupRow({
  group,
  onDone,
}: {
  group: HomeGroupSummary
  onDone: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [successor, setSuccessor] = useState('')
  const [former, setFormer] = useState<FormerLeaderStatus>('provider')
  const members = useQuery({
    queryKey: ['members', 1, '', group.id],
    queryFn: () => fetchMembers(1, undefined, group.id),
    enabled: open,
  })
  const change = useMutation({
    mutationFn: () => replaceLeader(group.id, successor, former),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['church-groups'] })
      await queryClient.invalidateQueries({ queryKey: ['members'] })
      setOpen(false)
      setSuccessor('')
      onDone(t('admin.groups.done', { leader: result.leader.name, group: result.group.name }))
    },
  })
  // The leader is not a choice: only the other members of the group.
  const candidates = (members.data?.items ?? []).filter((m) => m.full_name !== group.leader_name)
  return (
    <div>
      <h2>{group.name}</h2>
      <p>{t('admin.groups.leader', { name: group.leader_name })}</p>
      {!open ? (
        <button type="button" className="btn btn-quiet" onClick={() => setOpen(true)}>
          {t('admin.groups.replace', { group: group.name })}
        </button>
      ) : (
        <form
          className="form-grid"
          aria-label={t('admin.groups.replace', { group: group.name })}
          onSubmit={(event) => {
            event.preventDefault()
            if (successor) change.mutate()
          }}
        >
          {change.error && (
            <Alert kind="error" focus>
              {problem(change.error)}
            </Alert>
          )}
          {members.data && candidates.length === 0 ? (
            <p className="muted span-2">{t('admin.groups.nobody')}</p>
          ) : (
            <>
              <SelectField
                label={t('admin.groups.successor')}
                name={`successor-${group.id}`}
                value={successor}
                onChange={setSuccessor}
                options={[
                  { value: '', label: t('admin.groups.choose') },
                  ...candidates.map((m) => ({
                    value: m.id,
                    label: `${m.full_name} · ${t(`status.${m.status}`)}`,
                  })),
                ]}
              />
              <SelectField
                label={t('admin.groups.former')}
                name={`former-${group.id}`}
                value={former}
                onChange={(value) => setFormer(value as FormerLeaderStatus)}
                options={(['provider', 'searcher', 'keep'] as const).map((value) => ({
                  value,
                  label: t(`admin.groups.former.${value}`),
                }))}
              />
              <div className="form-actions span-2">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={change.isPending || !successor}
                >
                  {t('admin.groups.submit')}
                </button>
                <button type="button" className="btn btn-quiet" onClick={() => setOpen(false)}>
                  {t('common.cancel')}
                </button>
              </div>
            </>
          )}
        </form>
      )}
    </div>
  )
}
