import { t } from '../../i18n'

/** "45.5 AED per hour", or the "not set" text when the freelancer has no rate. */
export function formatRate(rate: number | null, currency: string | null): string {
  if (rate === null || currency === null) return t('common.none')
  return t('search.rate', {
    rate: rate.toLocaleString(undefined, { maximumFractionDigits: 2 }),
    currency,
  })
}
