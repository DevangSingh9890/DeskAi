import type { ChatMessage } from '../types/chat'
import { TicketRecommendationCard } from './TicketRecommendationCard'
import { AgentWorkflowCard } from './AgentWorkflowCard'
import { ClassificationCard } from './ClassificationCard'
import { KnowledgeSourcesCard } from './KnowledgeSourcesCard'
import { RecommendationCard } from './RecommendationCard'
import { TroubleshootingCard } from './TroubleshootingCard'
import { TransferToHumanCard } from './TransferToHumanCard'

interface MessageBubbleProps {
  message: ChatMessage
  onTicketDecision: (messageId: string, approved: boolean) => void
  onHandoff: (messageId: string) => void
  onContinueWithAI: (messageId: string) => void
  handoffPending: boolean
  handoffError: string | null
  handoffExists: boolean
}

function AssistantMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.8 13.8 9l6.2 1.8-6.2 1.8-1.8 6.2-1.8-6.2L4 10.8 10.2 9 12 2.8Z" />
      <path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
    </svg>
  )
}

export function MessageBubble({
  message,
  onTicketDecision,
  onHandoff,
  onContinueWithAI,
  handoffPending,
  handoffError,
  handoffExists,
}: MessageBubbleProps) {
  const isAssistant = message.role === 'assistant'

  return (
    <article
      className={`message-row ${isAssistant ? 'message-row--assistant' : 'message-row--user'}`}
    >
      {isAssistant && (
        <div className="message-avatar message-avatar--assistant">
          <AssistantMark />
        </div>
      )}
      <div className="message-content">
        <div className="message-meta">
          <span className="message-author">
            {isAssistant ? 'DeskAI Assistant' : 'You'}
          </span>
          <time
            className="message-time"
            dateTime={message.timestamp.toISOString()}
            title={message.timestamp.toLocaleString()}
          >
            {message.timestamp.toLocaleTimeString([], {
              hour: 'numeric',
              minute: '2-digit',
            })}
          </time>
        </div>
        {isAssistant && message.agentResponse ? (
          <>
            <AgentWorkflowCard
              completedAt={message.timestamp}
              durationMs={message.workflowDurationMs}
            />
            <div className="agent-result-grid">
              <ClassificationCard
                classification={message.agentResponse.classification}
              />
              <KnowledgeSourcesCard
                sources={message.agentResponse.knowledge_sources}
              />
              <TroubleshootingCard
                troubleshooting={message.agentResponse.troubleshooting}
              />
              <RecommendationCard
                recommendedAction={
                  message.agentResponse.recommended_action ??
                  message.agentResponse.troubleshooting?.recommended_action ??
                  message.agentResponse.troubleshooting?.escalation_recommendation
                }
                followUpSuggestions={
                  message.agentResponse.follow_up_suggestions ??
                  message.agentResponse.troubleshooting?.follow_up_suggestions
                }
                summary={message.agentResponse.summary ?? message.agentResponse.response ?? message.content}
              />
              <TicketRecommendationCard
                recommendation={message.agentResponse.ticket_recommendation}
                classification={message.agentResponse.classification}
                status={message.agentResponse.ticket_status}
                similarTickets={message.agentResponse.similar_tickets}
                approvalState={message.ticketApprovalState}
                approvalError={message.ticketApprovalError}
                createdTicket={message.createdTicket}
                onApprove={() => onTicketDecision(message.id, true)}
                onReject={() => onTicketDecision(message.id, false)}
              />
            </div>
            {message.handoffRecommended && !message.handoffDismissed && !handoffExists && (
              <TransferToHumanCard
                disabled={handoffPending}
                error={handoffError}
                onTransfer={() => onHandoff(message.id)}
                onContinue={() => onContinueWithAI(message.id)}
              />
            )}
          </>
        ) : (
          <>
            <div className={`message-bubble ${isAssistant ? 'message-bubble--assistant' : 'message-bubble--user'}`}>
              {message.content}
            </div>
            {isAssistant && message.classification && (
              <ClassificationCard classification={message.classification} />
            )}
          </>
        )}
      </div>
      {!isAssistant && (
        <div className="message-avatar message-avatar--user" aria-hidden="true">
          Y
        </div>
      )}
    </article>
  )
}
