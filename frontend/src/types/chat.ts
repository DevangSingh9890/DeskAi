export type MessageRole = 'assistant' | 'user'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  classification?: IncidentClassification
  agentResponse?: AgentChatResponse
  workflowDurationMs?: number
}

export interface ChatRequest {
  message: string
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
  troubleshooting?: AgentTroubleshooting | null
  response?: string | null
  recommended_action?: string | null
  follow_up_suggestions?: string[] | null
  summary?: string | null
}
