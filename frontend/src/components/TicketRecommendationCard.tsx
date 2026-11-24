import type {
  Ticket,
  TicketApprovalState,
  TicketRecommendation,
  TicketStatusInfo,
  SimilarTicket,
} from '../types/ticket'
import { ApprovalCard } from './ApprovalCard'
import { SimilarTicketsCard } from './SimilarTicketsCard'
import { TicketCreatedCard } from './TicketCreatedCard'
import { TicketStatusCard } from './TicketStatusCard'

interface TicketRecommendationCardProps {
  recommendation?: TicketRecommendation | null
  status?: TicketStatusInfo | null
  similarTickets?: SimilarTicket[] | null
  approvalState?: TicketApprovalState
  approvalError?: string
  createdTicket?: Ticket
  onApprove: () => void
  onReject: () => void
}

export function TicketRecommendationCard({
  recommendation,
  status,
  similarTickets,
  approvalState = 'pending',
  approvalError,
  createdTicket,
  onApprove,
  onReject,
}: TicketRecommendationCardProps) {
  if (!recommendation) return null

  if (recommendation.action === 'check_ticket_status') {
    return <TicketStatusCard status={status} />
  }

  if (recommendation.action === 'find_similar_incidents') {
    return <SimilarTicketsCard tickets={similarTickets ?? []} />
  }

  if (!recommendation.ticket_recommended && recommendation.action !== 'create_ticket') {
    return null
  }

  const canApprove =
    recommendation.ticket_recommended &&
    recommendation.requires_approval &&
    Boolean(recommendation.approval_id)

  return (
    <section className="ticket-recommendation-card">
      <div className="ticket-recommendation-heading">
        <span className="ticket-recommendation-icon" aria-hidden="true">✦</span>
        <div>
          <p className="ticket-eyebrow">SUPPORT</p>
          <h3>{recommendation.ticket_recommended ? 'Create a support ticket?' : 'More information needed'}</h3>
        </div>
      </div>
      <p
        className="ticket-recommendation-reason"
        role={recommendation.ticket_recommended ? undefined : 'status'}
      >
        {recommendation.ticket_recommended
          ? 'Would you like me to create a support ticket for this request?'
          : 'I need a little more information before I can create a support ticket. Please add a few details about the issue.'}
      </p>
      {createdTicket ? (
        <TicketCreatedCard ticket={createdTicket} />
      ) : canApprove ? (
        <ApprovalCard
          state={approvalState}
          error={approvalError}
          onApprove={onApprove}
          onReject={onReject}
        />
      ) : recommendation.ticket_recommended ? (
        <p className="ticket-inline-error" role="alert">
          I couldn’t prepare the ticket yet. Please try again.
        </p>
      ) : null}
    </section>
  )
}
