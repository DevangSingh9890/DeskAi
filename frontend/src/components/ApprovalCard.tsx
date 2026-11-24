import type { TicketApprovalState } from '../types/ticket'

interface ApprovalCardProps {
  state?: TicketApprovalState
  error?: string
  onApprove: () => void
  onReject: () => void
}

export function ApprovalCard({
  state = 'pending',
  error,
  onApprove,
  onReject,
}: ApprovalCardProps) {
  const isBusy = state === 'approving' || state === 'rejecting'

  if (state === 'rejected') {
    return (
      <div className="ticket-approval-result ticket-approval-result--rejected" role="status">
        No ticket was created.
      </div>
    )
  }

  return (
    <div className="ticket-approval-card">
      {error && <p className="ticket-inline-error" role="alert">{error}</p>}
      <div className="ticket-approval-actions">
        <button
          className="ticket-button ticket-button--approve"
          type="button"
          onClick={onApprove}
          disabled={isBusy}
        >
          {state === 'approving' ? 'Creating ticket…' : 'Create Ticket'}
        </button>
        <button
          className="ticket-button ticket-button--reject"
          type="button"
          onClick={onReject}
          disabled={isBusy}
        >
          {state === 'rejecting' ? 'Updating…' : 'Not now'}
        </button>
      </div>
      {isBusy && (
        <p className="ticket-approval-progress" role="status">
          {state === 'approving'
            ? 'Creating your support ticket…'
            : 'Updating your request…'}
        </p>
      )}
    </div>
  )
}
