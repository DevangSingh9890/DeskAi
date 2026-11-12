export type MessageRole = 'assistant' | 'user'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
}

export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  response: string
}
