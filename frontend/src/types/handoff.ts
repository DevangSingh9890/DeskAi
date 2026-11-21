export type HumanMessageSender = 'user' | 'agent' | 'system'
export type HumanConversationStatus =
  | 'Pending'
  | 'Waiting'
  | 'Assigned'
  | 'In Progress'
  | 'Resolved'
  | 'Closed'

export interface HumanConversation {
  id: number
  conversation_id: string
  ticket_id: string | null
  status: HumanConversationStatus
  priority: string
  category: string
  assigned_agent: string | null
  context: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type HumanConversationSummary = Omit<HumanConversation, 'context'>

export interface HumanChatMessage {
  id: number
  conversation_id: string
  sender_type: HumanMessageSender
  message: string
  created_at: string
}

export interface HumanConversationDetail {
  conversation: HumanConversation
  messages: HumanChatMessage[]
}

export interface HandoffTranscriptMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface CreateHandoffRequest {
  messages: HandoffTranscriptMessage[]
  context: Record<string, unknown>
  ticket_id: string | null
  priority: string
  category: string
}
