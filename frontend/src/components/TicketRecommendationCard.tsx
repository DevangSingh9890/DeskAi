import type {
  AgentClassification,
} from '../types/chat'
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
  classification?: AgentClassification | null
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
  classification,
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

  const isHighPriority =
    classification?.priority === 'High' || classification?.priority === 'Critical'
  const canApprove =
    recommendation.ticket_recommended &&
    recommendation.requires_approval &&
    Boolean(recommendation.approval_id)

  return (
    <section className="ticket-recommendation-card">
      <div className="ticket-recommendation-heading">
        <span className="ticket-recommendation-icon" aria-hidden="true">✦</span>
        <div>
          <p className="ticket-eyebrow">TICKET RECOMMENDATION</p>
          <h3>
            {!recommendation.ticket_recommended
              ? 'Ticket request needs more information'
              : isHighPriority
                ? 'High Priority Incident Detected'
                : 'Incident Tracking Recommended'}
          </h3>
        </div>
      </div>
      <p
        className="ticket-recommendation-reason"
        role={recommendation.ticket_recommended ? undefined : 'status'}
      >
        {recommendation.reason}
      </p>
      {recommendation.ticket_recommended && (
        <p className="ticket-recommendation-action">
          <span>Recommended Action</span>
          <strong>Create Incident</strong>
        </p>
      )}
      {classification && (
        <div className="ticket-recommendation-meta">
          {classification.priority && (
            <span className={`ticket-priority-pill ticket-priority-pill--${classification.priority.toLowerCase()}`}>
              {classification.priority} priority
            </span>
          )}
          {classification.assigned_group && <span>{classification.assigned_group}</span>}
        </div>
      )}
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
          Approval details are unavailable. Please submit the request again.
        </p>
      ) : null}
    </section>
  )
}
