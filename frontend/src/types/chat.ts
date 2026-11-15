export type MessageRole = 'assistant' | 'user'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  classification?: IncidentClassification
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
