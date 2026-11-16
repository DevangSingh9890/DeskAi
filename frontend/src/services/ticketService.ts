import axios from 'axios'

import { api } from './api'
import type {
  Ticket,
  TicketApprovalRequest,
  TicketApprovalResponse,
  TicketCreateRequest,
  TicketStatusInfo,
  TicketUpdateRequest,
  SimilarTicket,
} from '../types/ticket'

export async function getTickets(): Promise<Ticket[]> {
  const { data } = await api.get<Ticket[]>('/api/tickets')
  return data
}

export async function getTicket(ticketId: string): Promise<Ticket> {
  const { data } = await api.get<Ticket>(
    `/api/tickets/${encodeURIComponent(ticketId)}`,
  )
  return data
}

export async function createTicket(
  request: TicketCreateRequest,
): Promise<Ticket> {
  const { data } = await api.post<Ticket>('/api/tickets', request)
  return data
}

export async function approveTicket(
  request: TicketApprovalRequest,
): Promise<TicketApprovalResponse> {
  const { data } = await api.post<TicketApprovalResponse>(
    '/api/tickets/approve',
    request,
  )
  return data
}

export async function updateTicket(
  ticketId: string,
  request: TicketUpdateRequest,
): Promise<Ticket> {
  const { data } = await api.put<Ticket>(
    `/api/tickets/${encodeURIComponent(ticketId)}`,
    request,
  )
  return data
}

export async function getTicketStatus(
  ticketId: string,
): Promise<TicketStatusInfo> {
  const { data } = await api.get<TicketStatusInfo>(
    `/api/tickets/status/${encodeURIComponent(ticketId)}`,
  )
  return data
}

export async function searchSimilarTickets(
  query: string,
  category?: string,
  priority?: string,
): Promise<SimilarTicket[]> {
  const { data } = await api.get<SimilarTicket[]>('/api/tickets/similar', {
    params: { q: query, category, priority },
  })
  return data
}

export function getTicketErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    if (error.response?.data.detail) return error.response.data.detail
    if (error.code === 'ECONNABORTED') {
      return 'The ticket request took too long. Please try again.'
    }
    if (!error.response) {
      return 'Could not reach the ticket service. Check that the backend is running.'
    }
  }
  return 'The ticket request failed. Please try again.'
}
