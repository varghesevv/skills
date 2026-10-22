import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { listReports, listSchedules, updateSchedule } from '../../api/reports'
import type { ReportSchedule } from '../../api/types'
import { t } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, CheckboxField, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import type { FieldErrors } from '../../shared/validation'
import { ADMIN_REPORTS_KEY, ADMIN_SCHEDULES_KEY } from './keys'

function ScheduleCard({ schedule, title }: { schedule: ReportSchedule; title: string }) {
  const queryClient = useQueryClient()
  const [cron, setCron] = useState(schedule.cron_expression)
  const [zone, setZone] = useState(schedule.timezone)
  const [enabled, setEnabled] = useState(schedule.is_enabled)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: () =>
      updateSchedule(schedule.report_name, {
        cron_expression: cron.trim(),
        timezone: zone.trim(),
        is_enabled: enabled,
      }),
    onSuccess: async () => {
      setSaved(true)
      await queryClient.invalidateQueries({ queryKey: ADMIN_SCHEDULES_KEY })
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    const found: FieldErrors = {}
    if (cron.trim().split(/\s+/).length !== 5) found.cron = t('schedules.cronInvalid')
    if (zone.trim() === '') found.zone = t('validation.required')
    setErrors(found)
    if (Object.keys(found).length === 0) save.mutate()
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-grid cols-2" aria-label={title}>
      <h2 className="span-2">{title}</h2>
      {error && (
        <div className="span-2">
          <Alert kind="error" focus>
            {error}
          </Alert>
        </div>
      )}
      {saved && (
        <div className="span-2">
          <Alert kind="success">{t('common.saved')}</Alert>
        </div>
      )}
      <TextField
        label={t('schedules.cron')}
        name={`cron-${schedule.report_name}`}
        hint={t('schedules.cronHint')}
        value={cron}
        onChange={(value) => {
          setSaved(false)
          setCron(value)
        }}
        error={errors.cron}
      />
      <TextField
        label={t('schedules.timezone')}
        name={`tz-${schedule.report_name}`}
        hint={t('schedules.timezoneHint')}
        value={zone}
        onChange={(value) => {
          setSaved(false)
          setZone(value)
        }}
        error={errors.zone}
      />
      <div className="span-2">
        <CheckboxField
          label={t('schedules.enabled')}
          name={`enabled-${schedule.report_name}`}
          checked={enabled}
          onChange={(checked) => {
            setSaved(false)
            setEnabled(checked)
          }}
        />
      </div>
      <button type="submit" className="btn btn-primary span-2" disabled={save.isPending}>
        {save.isPending ? t('common.saving') : t('common.save')}
      </button>
    </form>
  )
}

export default function SchedulesPage() {
  usePageTitle(t('schedules.title'))
  const query = useQuery({ queryKey: ADMIN_SCHEDULES_KEY, queryFn: listSchedules })
  const reports = useQuery({ queryKey: ADMIN_REPORTS_KEY, queryFn: listReports })
  const titles = new Map((reports.data ?? []).map((report) => [report.name, report.title]))
  return (
    <>
      <h1>{t('schedules.title')}</h1>
      <p className="lead">{t('schedules.lead')}</p>
      <QueryBoundary query={query}>
        {(schedules) => (
          <div className="stack">
            {schedules.map((schedule) => (
              <ScheduleCard
                key={schedule.report_name}
                schedule={schedule}
                title={titles.get(schedule.report_name) ?? schedule.report_name}
              />
            ))}
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
