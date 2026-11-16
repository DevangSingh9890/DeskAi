export type TicketPriority = 'Critical' | 'High' | 'Medium' | 'Low'
export type TicketStatus =
  | 'Open'
  | 'In Progress'
  | 'Resolved'
  | 'Closed'

export type TicketApprovalState =
  | 'pending'
  | 'approving'
  | 'rejecting'
  | 'approved'
  | 'rejected'
  | 'failed'

export interface Ticket {
  ticket_id: string
  title: string
  description: string
  priority: TicketPriority
  status: TicketStatus
  category: string
  subcategory: string
  assigned_group: string
  created_at: string
  updated_at: string
  created_by: string
  resolution: string | null
}

export interface TicketCreateRequest {
  title: string
  description: string
  priority: TicketPriority
  category: string
  subcategory: string
  assigned_group: string
  created_by?: string
}

export interface TicketUpdateRequest {
  title?: string
  description?: string
  priority?: TicketPriority
  status?: TicketStatus
  category?: string
  subcategory?: string
  assigned_group?: string
  resolution?: string | null
}

export interface TicketRecommendation {
  action:
    | 'create_ticket'
    | 'check_ticket_status'
    | 'find_similar_incidents'
    | 'no_action'
  ticket_recommended: boolean
  reason: string
  requires_approval: boolean
  approval_id?: string | null
}

export interface SimilarTicket {
  ticket_id: string
  category: string
  priority: TicketPriority
  summary: string
  resolution: string | null
}

export interface TicketStatusInfo {
  ticket_id: string
  status: string
  assigned_group?: string | null
  updated_at?: string | null
}

export interface TicketApprovalRequest {
  approved: boolean
  message: string
  approval_id?: string
  ticket_details?: TicketCreateRequest
}

export interface TicketApprovalResponse {
  approved: boolean
  ticket_id: string | null
  status: string
  assigned_group: string | null
  ticket: Ticket | null
  message: string | null
}
