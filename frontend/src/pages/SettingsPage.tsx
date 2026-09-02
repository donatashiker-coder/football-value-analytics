import { useEffect, useState } from 'react'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useToast } from '@/hooks/useToast'
import type { SettingsValue } from '@/types'
import { titleCase } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/States'

const GROUP_ORDER = ['value', 'form_weights', 'goal_model', 'corner_model', 'staking', 'bankroll', 'alerts', 'scanner']

export default function SettingsPage() {
  const { data, loading, error, refetch } = useApi((signal) => api.settings(signal), [])

  if (loading) return <LoadingState label="Loading settings" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="Settings DATA UNAVAILABLE." />

  const keys = [...GROUP_ORDER.filter((k) => k in data.settings), ...Object.keys(data.settings).filter((k) => !GROUP_ORDER.includes(k))]

  return (
    <div>
      <PageHeader title="Settings" subtitle="Thresholds, weights and model parameters. Changes apply to the next scan." />
      <div className="grid gap-4 lg:grid-cols-2">
        {keys.map((k) => (
          <SettingsGroup key={k} groupKey={k} value={data.settings[k]} defaults={data.defaults[k] ?? {}} descriptions={data.descriptions} onSaved={refetch} />
        ))}
      </div>
    </div>
  )
}

type FieldValue = string | boolean | string[]

function toFields(v: SettingsValue): Record<string, FieldValue> {
  const out: Record<string, FieldValue> = {}
  for (const [k, val] of Object.entries(v)) {
    if (typeof val === 'boolean') out[k] = val
    else if (Array.isArray(val)) out[k] = val.map(String)
    else if (val === null || val === undefined) out[k] = ''
    else out[k] = String(val)
  }
  return out
}

function SettingsGroup({
  groupKey,
  value,
  defaults,
  descriptions,
  onSaved,
}: {
  groupKey: string
  value: SettingsValue
  defaults: SettingsValue
  descriptions: Record<string, string>
  onSaved: () => void
}) {
  const toast = useToast()
  const [fields, setFields] = useState<Record<string, FieldValue>>(() => toFields(value))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDefaults, setShowDefaults] = useState(false)

  useEffect(() => {
    setFields(toFields(value))
  }, [value])

  function set(k: string, v: FieldValue) {
    setFields((f) => ({ ...f, [k]: v }))
  }

  function buildPayload(): SettingsValue {
    const payload: SettingsValue = {}
    for (const [k, v] of Object.entries(fields)) {
      const original = value[k]
      if (typeof v === 'boolean') payload[k] = v
      else if (Array.isArray(v)) payload[k] = v.map((s) => s.trim()).filter(Boolean)
      else if (typeof original === 'number') {
        const n = Number(v)
        if (!Number.isFinite(n)) throw new Error(`${k} must be a number`)
        payload[k] = n
      } else payload[k] = v
    }
    return payload
  }

  async function save() {
    setError(null)
    setSaving(true)
    try {
      await api.updateSettings(groupKey, buildPayload())
      toast.push('success', `${titleCase(groupKey)} saved`)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function resetToDefaults() {
    setError(null)
    setFields(toFields(defaults))
    setShowDefaults(true)
  }

  const dirty = JSON.stringify(fields) !== JSON.stringify(toFields(value))

  return (
    <Section
      title={titleCase(groupKey)}
      actions={
        <div className="flex gap-1">
          <button type="button" className="btn-secondary btn-sm" onClick={resetToDefaults} title="Load default values into the form (not saved until you click Save)">
            Reset to defaults
          </button>
          <button type="button" className="btn-primary btn-sm" onClick={save} disabled={!dirty || saving}>
            {saving && <Spinner />}
            Save
          </button>
        </div>
      }
    >
      {descriptions[groupKey] && <p className="mb-2 text-xs muted">{descriptions[groupKey]}</p>}
      {showDefaults && <p className="mb-2 text-xs text-amber-700 dark:text-amber-300">Defaults loaded into the form. Click Save to apply them.</p>}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {Object.entries(fields).map(([k, v]) => {
          const id = `${groupKey}-${k}`
          const desc = descriptions[`${groupKey}.${k}`] ?? descriptions[k]
          const def = defaults[k]
          return (
            <div key={k}>
              <label className="label" htmlFor={id}>
                {titleCase(k)}
              </label>
              {typeof v === 'boolean' ? (
                <label className="flex items-center gap-2 text-sm">
                  <input id={id} type="checkbox" checked={v} onChange={(e) => set(k, e.target.checked)} />
                  {v ? 'Enabled' : 'Disabled'}
                </label>
              ) : Array.isArray(v) ? (
                <input id={id} className="input" value={v.join(', ')} onChange={(e) => set(k, e.target.value.split(','))} placeholder="comma separated" />
              ) : typeof value[k] === 'number' ? (
                <input id={id} type="number" step="any" className="input" value={v} onChange={(e) => set(k, e.target.value)} />
              ) : (
                <input id={id} className="input" value={v} onChange={(e) => set(k, e.target.value)} />
              )}
              <div className="mt-0.5 text-[11px] muted">
                {desc ? `${desc} ` : ''}
                {def !== undefined && <span>Default: {Array.isArray(def) ? def.join(', ') : String(def)}</span>}
              </div>
            </div>
          )
        })}
      </div>
      {error && (
        <div role="alert" className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      )}
    </Section>
  )
}
