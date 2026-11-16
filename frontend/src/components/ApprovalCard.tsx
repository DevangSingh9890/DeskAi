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
        Ticket recommendation declined.
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
          {state === 'approving' ? 'Creating ticket…' : 'Approve Ticket'}
        </button>
        <button
          className="ticket-button ticket-button--reject"
          type="button"
          onClick={onReject}
          disabled={isBusy}
        >
          {state === 'rejecting' ? 'Declining…' : 'Reject'}
        </button>
      </div>
      {isBusy && (
        <p className="ticket-approval-progress" role="status">
          {state === 'approving'
            ? 'Creating the approved incident…'
            : 'Saving your decision…'}
        </p>
      )}
    </div>
  )
}
