import { useState } from 'react'

import { getTicketErrorMessage } from '../services/ticketService'

interface AssignmentPanelProps {
  assignedGroup: string
  onSave: (assignedGroup: string) => Promise<void>
}

const assignmentGroups = [
  'Network Support',
  'Hardware Support',
  'Email Support',
  'Identity & Access Management',
  'Security Team',
  'Database Team',
  'Cloud Support',
  'Messaging Team',
]

export function AssignmentPanel({ assignedGroup, onSave }: AssignmentPanelProps) {
  const [selectedGroup, setSelectedGroup] = useState(assignedGroup)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function saveAssignment() {
    if (selectedGroup === assignedGroup || isSaving) return
    setIsSaving(true)
    setError(null)
    try {
      await onSave(selectedGroup)
    } catch (saveError: unknown) {
      setError(getTicketErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="drawer-section drawer-control-panel" aria-label="Assign ticket">
      <label htmlFor="ticket-assignment-select">Assigned group</label>
      <div className="drawer-control-row">
        <select
          id="ticket-assignment-select"
          value={selectedGroup}
          onChange={(event) => setSelectedGroup(event.target.value)}
        >
          {!assignmentGroups.includes(selectedGroup) && (
            <option value={selectedGroup}>{selectedGroup}</option>
          )}
          {assignmentGroups.map((group) => <option key={group} value={group}>{group}</option>)}
        </select>
        <button
          className="drawer-primary-button"
          type="button"
          disabled={selectedGroup === assignedGroup || isSaving}
          onClick={() => void saveAssignment()}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && <p className="drawer-inline-error" role="alert">{error}</p>}
    </section>
  )
}
