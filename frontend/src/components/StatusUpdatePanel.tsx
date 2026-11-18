import { useState } from 'react'

import { getTicketErrorMessage } from '../services/ticketService'
import type { TicketStatus } from '../types/ticket'

interface StatusUpdatePanelProps {
  status: TicketStatus
  onSave: (status: TicketStatus) => Promise<void>
}

const statuses: TicketStatus[] = ['Open', 'In Progress', 'Resolved', 'Closed']

export function StatusUpdatePanel({ status, onSave }: StatusUpdatePanelProps) {
  const [selectedStatus, setSelectedStatus] = useState(status)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function saveStatus() {
    if (selectedStatus === status || isSaving) return
    setIsSaving(true)
    setError(null)
    try {
      await onSave(selectedStatus)
    } catch (saveError: unknown) {
      setError(getTicketErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="drawer-section drawer-control-panel" aria-label="Update ticket status">
      <label htmlFor="ticket-status-select">Status</label>
      <div className="drawer-control-row">
        <select
          id="ticket-status-select"
          value={selectedStatus}
          onChange={(event) => setSelectedStatus(event.target.value as TicketStatus)}
        >
          {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <button
          className="drawer-primary-button"
          type="button"
          disabled={selectedStatus === status || isSaving}
          onClick={() => void saveStatus()}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && <p className="drawer-inline-error" role="alert">{error}</p>}
    </section>
  )
}
