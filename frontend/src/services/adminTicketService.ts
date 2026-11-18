import { api } from './api'
import type {
  AdminDashboardSummary,
  AdminTicketDetail,
  AdminTicketPage,
  Ticket,
  TicketAnalytics,
  TicketComment,
  TicketPriority,
  TicketStatus,
} from '../types/ticket'

export interface AdminTicketFilters {
  search: string
  status: TicketStatus | 'All'
  priority: TicketPriority | 'All'
  assignmentGroup: string
  sortBy: 'created_at' | 'updated_at' | 'priority' | 'status' | 'ticket_id'
  sortOrder: 'asc' | 'desc'
  page: number
  pageSize: number
}

export async function getAdminDashboard(): Promise<AdminDashboardSummary> {
  const { data } = await api.get<AdminDashboardSummary>('/api/admin/dashboard')
  return data
}

export async function getAdminTickets(
  filters: AdminTicketFilters,
): Promise<AdminTicketPage> {
  const { data } = await api.get<AdminTicketPage>('/api/admin/tickets', {
    params: {
      search: filters.search || undefined,
      status: filters.status === 'All' ? undefined : filters.status,
      priority: filters.priority === 'All' ? undefined : filters.priority,
      assignment_group: filters.assignmentGroup || undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
      page: filters.page,
      page_size: filters.pageSize,
    },
  })
  return data
}

export async function getAdminTicket(ticketId: string): Promise<AdminTicketDetail> {
  const { data } = await api.get<AdminTicketDetail>(
    `/api/admin/tickets/${encodeURIComponent(ticketId)}`,
  )
  return data
}

export async function getAdminTicketComments(
  ticketId: string,
): Promise<TicketComment[]> {
  const { data } = await api.get<TicketComment[]>(
    `/api/admin/tickets/${encodeURIComponent(ticketId)}/comments`,
  )
  return data
}

export async function updateAdminTicketStatus(
  ticketId: string,
  ticketStatus: TicketStatus,
): Promise<Ticket> {
  const { data } = await api.put<Ticket>(
    `/api/admin/tickets/${encodeURIComponent(ticketId)}/status`,
    { status: ticketStatus },
  )
  return data
}

export async function assignAdminTicket(
  ticketId: string,
  assignedGroup: string,
): Promise<Ticket> {
  const { data } = await api.put<Ticket>(
    `/api/admin/tickets/${encodeURIComponent(ticketId)}/assign`,
    { assigned_group: assignedGroup },
  )
  return data
}

export async function addAdminTicketComment(
  ticketId: string,
  body: string,
): Promise<TicketComment> {
  const { data } = await api.post<TicketComment>(
    `/api/admin/tickets/${encodeURIComponent(ticketId)}/comments`,
    { body },
  )
  return data
}

export async function getAdminAnalytics(): Promise<TicketAnalytics> {
  const { data } = await api.get<TicketAnalytics>('/api/admin/analytics')
  return data
}
