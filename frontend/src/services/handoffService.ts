import axios from 'axios'
import { api } from './api'
import type {
  CreateHandoffRequest,
  HumanChatMessage,
  HumanConversation,
  HumanConversationDetail,
  HumanConversationSummary,
} from '../types/handoff'

export async function createHandoff(
  request: CreateHandoffRequest,
): Promise<HumanConversation> {
  const { data } = await api.post<HumanConversation>('/api/handoff/request', request)
  return data
}

export async function getHumanConversations(): Promise<HumanConversationSummary[]> {
  const { data } = await api.get<HumanConversationSummary[]>('/api/handoff/requests')
  return data
}

export async function acceptHumanConversation(
  conversationId: string,
  agentName: string,
): Promise<HumanConversation> {
  const { data } = await api.post<HumanConversation>(
    `/api/handoff/${encodeURIComponent(conversationId)}/accept`,
    { agent_name: agentName },
  )
  return data
}

export async function getHumanConversation(
  conversationId: string,
): Promise<HumanConversationDetail> {
  const { data } = await api.get<HumanConversationDetail>(
    `/api/handoff/${encodeURIComponent(conversationId)}/messages`,
  )
  return data
}

export async function sendHumanMessage(
  conversationId: string,
  senderType: 'user' | 'agent',
  message: string,
): Promise<HumanChatMessage> {
  const { data } = await api.post<HumanChatMessage>(
    `/api/handoff/${encodeURIComponent(conversationId)}/messages`,
    { sender_type: senderType, message },
  )
  return data
}

export async function resolveHumanConversation(
  conversationId: string,
): Promise<HumanConversation> {
  const { data } = await api.post<HumanConversation>(
    `/api/handoff/${encodeURIComponent(conversationId)}/resolve`,
  )
  return data
}

export function getHandoffErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail
  }
  return 'Human support is unavailable right now. Please try again.'
}

export function isHandoffNotFound(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404
}
