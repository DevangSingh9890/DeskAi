import axios from 'axios'
import type {
  AgentChatResponse,
  AgentRefinementContext,
  ChatRequest,
  ChatResponse,
} from '../types/chat'

export interface PerformanceStatus {
  warming: boolean
  embedding_model_loaded: boolean
  model: string
  warmup_started_at: string | null
  warmup_completed_at: string | null
  warmup_status: 'not_started' | 'warming' | 'completed' | 'failed'
  warmup_error: string | null
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  timeout: 30_000,
})

export async function getPerformanceStatus(): Promise<PerformanceStatus> {
  const { data } = await api.get<PerformanceStatus>('/api/debug/performance')
  return data
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const request: ChatRequest = { message }
  const { data } = await api.post<ChatResponse>('/api/chat', request)
  return data
}

export async function sendAgentChatMessage(
  message: string,
  refinementContext?: AgentRefinementContext,
): Promise<AgentChatResponse> {
  const request: ChatRequest & {
    refinement_context?: AgentRefinementContext
  } = {
    message,
    ...(refinementContext ? { refinement_context: refinementContext } : {}),
  }
  const { data } = await api.post<AgentChatResponse>(
    '/api/agent/chat',
    request,
    refinementContext ? { timeout: 35_000 } : undefined,
  )
  return data
}

export function getChatErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    if (error.response?.data.detail) {
      return error.response.data.detail
    }

    if (error.code === 'ECONNABORTED') {
      return 'The backend did not respond within the chat request limit. Check backend and Groq latency before retrying.'
    }

    if (!error.response) {
      return 'Could not reach the service desk. Check that the backend is running and try again.'
    }
  }

  return 'Something went wrong while sending your message. Please try again.'
}
