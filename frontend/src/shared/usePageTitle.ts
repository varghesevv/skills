import { useEffect } from 'react'

import { t } from '../i18n'

export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · ${t('app.name')}`
  }, [title])
}
