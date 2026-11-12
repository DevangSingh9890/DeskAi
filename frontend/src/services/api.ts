import axios from 'axios'
import type { ChatRequest, ChatResponse } from '../types/chat'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  timeout: 30_000,
})

export async function sendChatMessage(message: string): Promise<string> {
  const request: ChatRequest = { message }
  const { data } = await api.post<ChatResponse>('/api/chat', request)
  return data.response
}

export function getChatErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    if (error.response?.data.detail) {
      return error.response.data.detail
    }

    if (error.code === 'ECONNABORTED') {
      return 'The request took too long. Please try again.'
    }

    if (!error.response) {
      return 'Could not reach the service desk. Check that the backend is running and try again.'
    }
  }

  return 'Something went wrong while sending your message. Please try again.'
}
