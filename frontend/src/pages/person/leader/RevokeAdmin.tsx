import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../../../api/http'
import { fetchMembers, revokePerson } from '../../../api/person'
import type { PersonDetail } from '../../../api/types'
import { Confirm, useReturnFocus } from '../../../shared/Confirm'
import { errorMessage } from '../../../shared/errors'
import { Alert, SelectField } from '../../../shared/ui'
import { t } from '../../../i18n'
import { leaderProblem } from './problems'
import { REVOCATION_KEYS } from './refreshKeys'
import type { Change } from './StatusControls'

/** What a refused revocation of an ADMIN means. The server's code decides the words. */
function problem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'successor_required') return t('revokeAdmin.error.needChoice')
    if (error.code === 'successor_not_member') return t('revokeAdmin.error.member')
  }
  return leaderProblem(error)
}

/** The OWNER revokes the ADMIN of a church. The church needs a new ADMIN from its members in the
 *  same step, and the group the ADMIN leads needs a leader from that group (or closes, when the
 *  ADMIN is alone in it). The server refuses anything else. */
export default function RevokeAdmin({
  person,
  onDone,
}: {
  person: PersonDetail
  onDone: (message: string, change: Change) => void
}) {
  const queryClient = useQueryClient()
  const name = person.full_name
  const [confirming, setConfirming] = useState(false)
  const opener = useReturnFocus<HTMLButtonElement>(confirming)
  const [successor, setSuccessor] = useState('')
  const [groupSuccessor, setGroupSuccessor] = useState('')
  const churchMembers = useQuery({
    queryKey: ['members', 1, '', '', person.church.id],
    queryFn: () => fetchMembers(1, undefined, undefined, person.church.id),
    enabled: confirming,
  })
  const groupMembers = useQuery({
    queryKey: ['members', 1, '', person.home_group?.id ?? ''],
    queryFn: () => fetchMembers(1, undefined, person.home_group?.id),
    enabled: confirming && !!person.home_group,
  })
  const revoke = useMutation({
    mutationFn: () => revokePerson(person.id, successor, groupSuccessor || undefined),
    onSuccess: async () => {
      for (const key of REVOCATION_KEYS) await queryClient.invalidateQueries({ queryKey: [key] })
      setConfirming(false)
      onDone(t('leader.revoke.done', { name }), {
        status: 'revoked',
        home_group: null,
        flagged_for_recheck: false,
        requested_status: null,
      })
    },
  })
  const close = () => {
    revoke.reset()
    setSuccessor('')
    setGroupSuccessor('')
    setConfirming(false)
  }
  const inChurch = (churchMembers.data?.items ?? []).filter((m) => m.id !== person.id)
  const inGroup = (groupMembers.data?.items ?? []).filter((m) => m.id !== person.id)
  const loading = churchMembers.isPending || (!!person.home_group && groupMembers.isPending)
  const failed = churchMembers.isError ? churchMembers : groupMembers.isError ? groupMembers : null
  const nobodyInChurch = churchMembers.isSuccess && inChurch.length === 0
  const needsGroup = inGroup.length > 0
  const ready =
    !loading && !failed && !nobodyInChurch && !!successor && (!needsGroup || !!groupSuccessor)
  const options = (rows: typeof inChurch) => [
    { value: '', label: t('revokeAdmin.choose') },
    ...rows.map((m) => ({ value: m.id, label: `${m.full_name} · ${t(`status.${m.status}`)}` })),
  ]
  const cut = (data: { total: number; items: unknown[] } | undefined) =>
    data && data.total > data.items.length ? (
      <p className="hint">
        {t('revokeAdmin.more', { count: data.items.length, total: data.total })}
      </p>
    ) : null

  return (
    <div className="span-2">
      {revoke.error && !confirming && (
        <Alert kind="error" focus>
          {problem(revoke.error)}
        </Alert>
      )}
      {!confirming ? (
        <div className="form-actions">
          <button
            ref={opener}
            type="button"
            className="btn btn-quiet"
            onClick={() => setConfirming(true)}
          >
            {t('revokeAdmin.open', { name })}
          </button>
        </div>
      ) : (
        <Confirm
          label={t('revokeAdmin.open', { name })}
          warning={t('revokeAdmin.warning', { name, church: person.church.name })}
          confirmLabel={t('leader.revoke.confirm')}
          busy={revoke.isPending}
          confirmDisabled={!ready}
          onConfirm={() => revoke.mutate()}
          onCancel={close}
        >
          {revoke.error && (
            <Alert kind="error" focus>
              {problem(revoke.error)}
            </Alert>
          )}
          {loading && (
            <p role="status" className="muted">
              {t('loading')}
            </p>
          )}
          {failed && (
            <Alert kind="error">
              <p>{errorMessage(failed.error)}</p>
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => {
                  void churchMembers.refetch()
                  if (person.home_group) void groupMembers.refetch()
                }}
              >
                {t('common.retry')}
              </button>
            </Alert>
          )}
          {nobodyInChurch && <p className="hint">{t('revokeAdmin.noMembers')}</p>}
          {churchMembers.isSuccess && inChurch.length > 0 && (
            <>
              {cut(churchMembers.data)}
              <SelectField
                label={t('revokeAdmin.successor', { church: person.church.name })}
                name="revoke-admin-successor"
                value={successor}
                onChange={setSuccessor}
                options={options(inChurch)}
              />
            </>
          )}
          {groupMembers.isSuccess && !needsGroup && (
            <p className="hint">{t('revokeAdmin.groupAlone')}</p>
          )}
          {groupMembers.isSuccess && needsGroup && (
            <>
              {cut(groupMembers.data)}
              <SelectField
                label={t('revokeAdmin.group', { name })}
                name="revoke-admin-group"
                value={groupSuccessor}
                onChange={setGroupSuccessor}
                options={options(inGroup)}
              />
            </>
          )}
        </Confirm>
      )}
    </div>
  )
}
