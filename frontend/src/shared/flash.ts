/** One message that survives a change of page, shown by the page that follows. It is kept in
 *  memory, not in the address or the browser's storage. Used when an action changes who the person
 *  is, so the guard of the page they were on sends them home before they can read it.
 *
 *  The page that follows may be mounted more than once while who the person is settles, so the
 *  message is kept for a few seconds rather than handed out once. */
const KEEP_MS = 10_000
let message: { text: string; at: number } | null = null

export function setFlash(text: string): void {
  message = { text, at: Date.now() }
}

/** The message, while it is fresh; older ones are dropped. */
export function takeFlash(now: number = Date.now()): string | null {
  if (message && now - message.at > KEEP_MS) message = null
  return message ? message.text : null
}

/** Forget it: for a test, or when the person has read it. */
export function clearFlash(): void {
  message = null
}
