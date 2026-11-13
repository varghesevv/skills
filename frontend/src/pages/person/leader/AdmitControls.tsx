import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { admitPerson, declinePerson } from '../../../api/person'
import type { AppliedStatus, PersonStatus } from '../../../api/types'
import { t } from '../../../i18n'
import { Alert } from '../../../shared/ui'
import { leaderProblem } from './problems'

export type Outcome = 'declined' | { status: PersonStatus; requested_status: AppliedStatus | null }

/** Admit as a searcher or a provider, or decline (which asks first, because it cannot be undone).
 *  `canAdmitAsProvider` only switches the provider button off; the server decides.
 *  `upgrade` is for a searcher who asks to become a provider: only the provider admission is
 *  offered, and declining ends the request and leaves them a searcher. */
export default function AdmitControls({
  id,
  name,
  canAdmitAsProvider,
  upgrade = false,
  onDone,
}: {
  id: string
  name: string
  canAdmitAsProvider: boolean
  upgrade?: boolean
  onDone: (message: string, outcome: Outcome) => void
}) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['applicants'] })
    await queryClient.invalidateQueries({ queryKey: ['members'] })
  }
  const admit = useMutation({
    mutationFn: (to: 'searcher' | 'provider') => admitPerson(id, to),
    onSuccess: async (result) => {
      await refresh()
      onDone(t('leader.admit.done', { name }), {
        status: result.status,
        requested_status: result.requested_status,
      })
    },
  })
  const decline = useMutation({
    mutationFn: () => declinePerson(id),
    onSuccess: async () => {
      await refresh()
      onDone(
        upgrade ? t('leader.upgrade.declined', { name }) : t('leader.decline.done', { name }),
        upgrade ? { status: 'searcher', requested_status: null } : 'declined',
      )
    },
  })
  const busy = admit.isPending || decline.isPending
  const failure = admit.error ?? decline.error

  return (
    <div className="form-grid">
      {failure && (
        <Alert kind="error" focus>
          {leaderProblem(failure)}
        </Alert>
      )}
      {!confirming ? (
        <div className="form-actions span-2">
          {!upgrade && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => admit.mutate('searcher')}
            >
              {t('leader.admit.searcher', { name })}
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || !canAdmitAsProvider}
            aria-describedby={!canAdmitAsProvider ? `hint-${id}` : undefined}
            onClick={() => admit.mutate('provider')}
          >
            {t('leader.admit.provider', { name })}
          </button>
          <button
            type="button"
            className="btn btn-quiet"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            {upgrade ? t('leader.upgrade.decline', { name }) : t('leader.decline.open', { name })}
          </button>
          {!canAdmitAsProvider && (
            <p className="hint span-2" id={`hint-${id}`}>
              {t('leader.admit.providerHint')}
            </p>
          )}
        </div>
      ) : (
        <div className="span-2" role="group" aria-label={t('leader.decline.open', { name })}>
          <p>
            {upgrade
              ? t('leader.upgrade.warning', { name })
              : t('leader.decline.warning', { name })}
          </p>
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => decline.mutate()}
            >
              {t('leader.decline.confirm')}
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
