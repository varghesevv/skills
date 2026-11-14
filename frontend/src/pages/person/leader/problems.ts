import { ApiError } from '../../../api/http'
import { t } from '../../../i18n'
import { errorMessage } from '../../../shared/errors'

/** What a refused admit or decline means for a leader. The server's code decides the words. */
export function leaderProblem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'not_enough_vouches') return t('leader.error.notEnough')
    if (error.code === 'not_pending') return t('leader.error.notPending')
    if (error.code === 'status_not_allowed') return t('leader.error.notAllowed')
    if (error.code === 'already_revoked') return t('leader.error.alreadyRevoked')
    if (error.code === 'not_revoked') return t('leader.error.notRevoked')
    if (error.code === 'not_flagged') return t('leader.error.notFlagged')
    if (error.code === 'successor_required') return t('leader.error.successor')
    if (error.code === 'state_changed') return t('leader.error.changed')
  }
  return errorMessage(error)
}
