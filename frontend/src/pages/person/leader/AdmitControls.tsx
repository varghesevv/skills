import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { admitPerson, declinePerson } from '../../../api/person'
import { t } from '../../../i18n'
import { Alert } from '../../../shared/ui'
import { leaderProblem } from './problems'

/** Admit as a searcher or a provider, or decline (which asks first, because it cannot be undone).
 *  `liveVouches` only switches off what cannot work: a provider needs a vouch besides the leader's. */
export default function AdmitControls({
  id,
  name,
  liveVouches,
  onDone,
}: {
  id: string
  name: string
  liveVouches: number
  onDone: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['applicants'] })
    await queryClient.invalidateQueries({ queryKey: ['members'] })
  }
  const admit = useMutation({
    mutationFn: (to: 'searcher' | 'provider') => admitPerson(id, to),
    onSuccess: async () => {
      await refresh()
      onDone(t('leader.admit.done', { name }))
    },
  })
  const decline = useMutation({
    mutationFn: () => declinePerson(id),
    onSuccess: async () => {
      await refresh()
      onDone(t('leader.decline.done', { name }))
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
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => admit.mutate('searcher')}
          >
            {t('leader.admit.searcher', { name })}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || liveVouches === 0}
            aria-describedby={liveVouches === 0 ? `hint-${id}` : undefined}
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
            {t('leader.decline.open', { name })}
          </button>
          {liveVouches === 0 && (
            <p className="hint span-2" id={`hint-${id}`}>
              {t('leader.admit.providerHint')}
            </p>
          )}
        </div>
      ) : (
        <div className="span-2" role="group" aria-label={t('leader.decline.open', { name })}>
          <p>{t('leader.decline.warning', { name })}</p>
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
