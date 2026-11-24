import type {
  SimilarTicket,
  Ticket,
  TicketApprovalState,
  TicketRecommendation,
  TicketStatusInfo,
} from './ticket'

export type MessageRole = 'assistant' | 'user'
export type AnswerSatisfaction = 'helpful' | 'not_helpful'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  classification?: IncidentClassification
  agentResponse?: AgentChatResponse
  originalUserMessage?: string
  ticketApprovalState?: TicketApprovalState
  ticketApprovalError?: string
  createdTicket?: Ticket
  handoffRecommended?: boolean
  handoffDismissed?: boolean
  satisfaction?: AnswerSatisfaction
}

export interface ChatRequest {
  message: string
}

export interface AgentRefinementContext {
  original_question: string
  previous_response: string
  conversation_history: Array<{
    role: MessageRole
    content: string
    satisfaction?: AnswerSatisfaction
  }>
  classification: AgentClassification
  troubleshooting: AgentTroubleshooting
  knowledge_sources: string[]
  knowledge_results: Array<{
    content: string
    metadata: Record<string, string>
    score: number
  }>
  ticket_recommendation?: TicketRecommendation | null
  similar_tickets?: SimilarTicket[]
  ticket_status?: TicketStatusInfo | null
}

export interface IncidentClassification {
  issue: string
  category:
    | 'Network'
    | 'Software'
    | 'Hardware'
    | 'Email'
    | 'Access Management'
    | 'Security'
    | 'Database'
    | 'Cloud'
    | 'Collaboration Tools'
  subcategory: string
  priority: 'Critical' | 'High' | 'Medium' | 'Low'
  impact: 'Single User' | 'Multiple Users' | 'Department' | 'Organization'
  assigned_group: string
  confidence_score: number
}

export interface ChatResponse {
  response: string
  classification: IncidentClassification
}

export interface AgentClassification {
  issue?: string | null
  category?: string | null
  subcategory?: string | null
  priority?: string | null
  impact?: string | null
  assigned_group?: string | null
  confidence?: number | null
  confidence_score?: number | null
}

export interface AgentTroubleshooting {
  likely_cause?: string | null
  troubleshooting_steps?: string[] | null
  escalation_recommendation?: string | null
  recommended_action?: string | null
  follow_up_suggestions?: string[] | null
}

export interface AgentChatResponse {
  classification?: AgentClassification | null
  knowledge_sources?: string[] | null
  knowledge_results?: Array<{
    content: string
    metadata: Record<string, string>
    score: number
  }> | null
  troubleshooting?: AgentTroubleshooting | null
  response?: string | null
  recommended_action?: string | null
  follow_up_suggestions?: string[] | null
  summary?: string | null
  ticket_recommendation?: TicketRecommendation | null
  similar_tickets?: SimilarTicket[] | null
  ticket_status?: TicketStatusInfo | null
}
