import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { revealMobile } from '../../api/workhost'
import { t } from '../../i18n'
import { errorMessage } from '../../shared/errors'

/** Shown instead of the number until the work host asks for it. It is not the real number. */
const MASK = '+•• ••• ••• ••••'

/** True on phones and tablets, where revealing opens the dialler instead of showing the number. */
export function prefersDialler(): boolean {
  try {
    return window.matchMedia('(hover: none) and (pointer: coarse)').matches
  } catch {
    return false
  }
}

type Props = {
  freelancerId: string
  freelancerName: string
  source: 'search' | 'detail'
  /** The skills of the search that led here, so reports can show what people looked for. */
  searchedSkills?: string[]
}

/**
 * A greyed-out number with a Reveal button. The number comes from the server only after the
 * button is pressed, is kept in this component's state alone, and is never cached.
 */
export default function RevealMobile({
  freelancerId,
  freelancerName,
  source,
  searchedSkills = [],
}: Props) {
  const [revealed, setRevealed] = useState<{ number: string; dial: boolean } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const link = useRef<HTMLAnchorElement>(null)

  const reveal = useMutation({
    mutationFn: (dial: boolean) =>
      revealMobile(freelancerId, {
        channel: dial ? 'dial' : 'show',
        source,
        searched_skills: searchedSkills.slice(0, 10),
      }),
    onSuccess: (data, dial) => setRevealed({ number: data.mobile_number, dial }),
    onError: (failure) => setError(errorMessage(failure)),
  })

  // On a phone the dialler opens as soon as the number arrives.
  const shouldDial = revealed?.dial ?? false
  useEffect(() => {
    if (shouldDial) link.current?.click()
  }, [shouldDial])

  if (revealed) {
    return (
      <span className="reveal">
        <a
          ref={link}
          href={`tel:${revealed.number}`}
          aria-label={t('reveal.callLabel', { number: revealed.number })}
        >
          {revealed.number}
        </a>
      </span>
    )
  }

  return (
    <span className="reveal">
      <span className="reveal-mask" aria-hidden="true">
        {MASK}
      </span>
      <span className="sr-only">{t('reveal.hidden')}</span>
      <button
        type="button"
        className="btn btn-quiet reveal-button"
        aria-label={t('reveal.buttonFor', { name: freelancerName })}
        disabled={reveal.isPending}
        onClick={() => {
          setError(null)
          reveal.mutate(prefersDialler())
        }}
      >
        {reveal.isPending ? t('reveal.working') : t('reveal.button')}
      </button>
      {error && (
        <span className="reveal-error" role="alert">
          {error}
        </span>
      )}
    </span>
  )
}
