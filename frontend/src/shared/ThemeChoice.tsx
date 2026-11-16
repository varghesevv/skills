import { useState } from 'react'

import { t, type StringKey } from '../i18n'
import { applyTheme, savedTheme, type ThemeChoice as Choice } from './theme'

const CHOICES: { value: Choice; label: StringKey }[] = [
  { value: 'system', label: 'theme.system' },
  { value: 'light', label: 'theme.light' },
  { value: 'dark', label: 'theme.dark' },
]

/** System, light or dark, kept in this browser. */
export default function ThemeChoice() {
  const [choice, setChoice] = useState<Choice>(savedTheme)
  return (
    <fieldset className="plain-fieldset">
      <legend>{t('theme.title')}</legend>
      <div className="theme-choice">
        {CHOICES.map((item) => (
          <label key={item.value} className="choice">
            <input
              type="radio"
              name="theme"
              value={item.value}
              checked={choice === item.value}
              onChange={() => {
                setChoice(item.value)
                applyTheme(item.value)
              }}
            />
            {t(item.label)}
          </label>
        ))}
      </div>
      <p className="field-hint">{t('theme.hint')}</p>
    </fieldset>
  )
}
