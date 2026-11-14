import { usePerson } from '../../../auth/AuthContext'
import { t } from '../../../i18n'
import RatingsList from '../../../shared/RatingsList'
import { usePageTitle } from '../../../shared/usePageTitle'

/** The ratings a provider has received (the people who gave them are not shown). */
export default function MyRatings() {
  usePageTitle(t('ratings.title'))
  const person = usePerson()
  return (
    <div className="container">
      <div className="card">
        <h1>{t('ratings.title')}</h1>
        <p className="lead">{t('ratings.lead')}</p>
        <RatingsList freelancerId={person.id} />
      </div>
    </div>
  )
}
