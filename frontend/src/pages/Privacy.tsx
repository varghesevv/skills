import { t } from '../i18n'
import { usePageTitle } from '../shared/usePageTitle'

const SECTIONS = ['who', 'keep', 'see', 'close', 'long', 'more', 'tools', 'choices'] as const

/** The privacy statement: public, so the app and the sign-up page can point to it. */
export default function Privacy() {
  usePageTitle(t('privacy.title'))
  return (
    <div className="container">
      <div className="card">
        <h1>{t('privacy.title')}</h1>
        <p>{t('privacy.lead')}</p>
        {SECTIONS.map((key) => (
          <section key={key}>
            <h2>{t(`privacy.${key}.title`)}</h2>
            <p>{t(`privacy.${key}.text`)}</p>
          </section>
        ))}
      </div>
    </div>
  )
}
