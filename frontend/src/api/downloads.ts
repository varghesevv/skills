import { request, requestFile } from './http'

export type DownloadItem = {
  platform: string
  version: string
  build: number
  released_at: string
  size_bytes: number
  sha256: string
  notes: string
  filename: string
}

/** The published test builds of the Android app, newest first (any signed-in person). */
export const listDownloads = () => request<{ items: DownloadItem[] }>('/app/downloads')

/** One build, fetched with the bearer token: there is no public address for a file. */
export const fetchBuild = (item: DownloadItem) =>
  requestFile(`/app/downloads/android/${item.version}`, item.filename)
