import { useMutation, useQuery } from '@tanstack/react-query'

import { fetchBuild, listDownloads } from '../../api/downloads'
import type { DownloadItem } from '../../api/downloads'
import { t } from '../../i18n'
import { formatDateTime } from '../../shared/dates'
import { saveFile } from '../../shared/download'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'

/** The test builds of the Android app, for any signed-in person who is not revoked. */
export default function Downloads() {
  usePageTitle(t('downloads.title'))
  const list = useQuery({ queryKey: ['downloads'], queryFn: listDownloads })
  const download = useMutation({
    mutationFn: async (item: DownloadItem) => saveFile(await fetchBuild(item)),
  })

  return (
    <div className="container">
      <div className="card">
        <h1>{t('downloads.title')}</h1>
        <p>{t('downloads.lead')}</p>
        {download.error && (
          <Alert kind="error" focus>
            {errorMessage(download.error)}
          </Alert>
        )}
        <QueryBoundary query={list}>
          {(data) =>
            data.items.length === 0 ? (
              <p className="muted">{t('downloads.none')}</p>
            ) : (
              <ul className="plain-list">
                {data.items.map((item) => (
                  <li key={`${item.version}-${item.build}`}>
                    <h2>{t('downloads.version', { version: item.version, build: item.build })}</h2>
                    <p className="muted">
                      <time dateTime={item.released_at}>{formatDateTime(item.released_at)}</time>
                      {' · '}
                      {t('downloads.size', { size: (item.size_bytes / (1024 * 1024)).toFixed(1) })}
                    </p>
                    {item.notes && <p>{item.notes}</p>}
                    <p className="muted">
                      {t('downloads.sha256')}: <code>{item.sha256}</code>
                    </p>
                    <button
                      type="button"
                      className="btn"
                      disabled={download.isPending}
                      onClick={() => download.mutate(item)}
                    >
                      {t('downloads.download', { version: item.version })}
                    </button>
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
