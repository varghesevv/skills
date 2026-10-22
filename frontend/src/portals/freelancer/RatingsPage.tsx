import { useUser } from '../../auth/AuthContext'
import { t } from '../../i18n'
import RatingsList from '../../shared/RatingsList'
import { usePageTitle } from '../../shared/usePageTitle'

export default function RatingsPage() {
  usePageTitle(t('ratings.title'))
  const user = useUser()
  return (
    <>
      <h1>{t('ratings.title')}</h1>
      <p className="lead">{t('ratings.lead')}</p>
      <RatingsList freelancerId={user.id} />
    </>
  )
}
