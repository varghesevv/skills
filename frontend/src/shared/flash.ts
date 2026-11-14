/** One message that survives a change of page, shown once by the page that follows. It is kept in
 *  memory, not in the address or the browser's storage, and read once. Used when an action changes
 *  who the person is, so the guard of the page they were on sends them home before they can read it. */
let message: string | null = null

export function setFlash(text: string): void {
  message = text
}

export function takeFlash(): string | null {
  const text = message
  message = null
  return text
}
