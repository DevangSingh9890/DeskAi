import { useCallback, useEffect, useState } from 'react'

import {
  addAdminTicketComment,
  assignAdminTicket,
  getAdminTicket,
  getAdminTicketComments,
  updateAdminTicketStatus,
} from '../services/adminTicketService'
import { getTicketErrorMessage } from '../services/ticketService'
import { displayTicketNumber } from '../types/ticket'
import type {
  AdminTicketDetail,
  Ticket,
  TicketComment as TicketCommentType,
  TicketStatus,
} from '../types/ticket'
import { AssignmentPanel } from './AssignmentPanel'
import { StatusUpdatePanel } from './StatusUpdatePanel'
import { TicketComments } from './TicketComments'
import { TicketHistory } from './TicketHistory'

interface TicketDetailsDrawerProps {
  ticket: Ticket
  onClose: () => void
  onUpdated: () => void
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function TicketDetailsDrawer({
  ticket,
  onClose,
  onUpdated,
}: TicketDetailsDrawerProps) {
  const [details, setDetails] = useState<AdminTicketDetail | null>(null)
  const [comments, setComments] = useState<TicketCommentType[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshDetails = useCallback(async () => {
    const [ticketDetails, ticketComments] = await Promise.all([
      getAdminTicket(ticket.ticket_id),
      getAdminTicketComments(ticket.ticket_id),
    ])
    setDetails(ticketDetails)
    setComments(ticketComments)
  }, [ticket.ticket_id])

  useEffect(() => {
    let active = true
    void Promise.all([
      getAdminTicket(ticket.ticket_id),
      getAdminTicketComments(ticket.ticket_id),
    ])
      .then(([ticketDetails, ticketComments]) => {
        if (active) {
          setDetails(ticketDetails)
          setComments(ticketComments)
          setError(null)
        }
      })
      .catch((loadError: unknown) => {
        if (active) setError(getTicketErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [refreshDetails, ticket.ticket_id])

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  async function saveStatus(status: TicketStatus) {
    const updated = await updateAdminTicketStatus(ticket.ticket_id, status)
    setDetails((existing) => ({
      ...(existing ?? ticket),
      ...updated,
      comments,
      history: existing?.history ?? [],
    }))
    onUpdated()
    await refreshAfterPersistedChange('Status was updated')
  }

  async function saveAssignment(assignedGroup: string) {
    const updated = await assignAdminTicket(ticket.ticket_id, assignedGroup)
    setDetails((existing) => ({
      ...(existing ?? ticket),
      ...updated,
      comments,
      history: existing?.history ?? [],
    }))
    onUpdated()
    await refreshAfterPersistedChange('Assignment was updated')
  }

  async function postComment(body: string) {
    const comment = await addAdminTicketComment(ticket.ticket_id, body)
    setComments((existing) => [...existing, comment])
    onUpdated()
    await refreshAfterPersistedChange('Comment was saved')
  }

  async function refreshAfterPersistedChange(message: string) {
    try {
      await refreshDetails()
    } catch (loadError: unknown) {
      setError(
        `${message}, but ticket details could not be refreshed: ${getTicketErrorMessage(loadError)}`,
      )
    }
  }

  const current = details ?? ticket

  return (
    <div className="ticket-drawer-layer">
      <button
        className="ticket-drawer-backdrop"
        type="button"
        aria-label="Close ticket details"
        onClick={onClose}
      />
      <aside className="ticket-details-drawer" role="dialog" aria-modal="true" aria-labelledby="ticket-drawer-title">
        <header className="ticket-drawer-header">
          <div>
            <p className="ticket-eyebrow">INCIDENT DETAILS</p>
            <h2 id="ticket-drawer-title">{displayTicketNumber(ticket)}</h2>
          </div>
          <button className="ticket-drawer-close" type="button" onClick={onClose} aria-label="Close details">
            ×
          </button>
        </header>
        {error && <div className="ticket-page-error" role="alert">{error}</div>}
        {isLoading ? (
          <div className="tickets-loading" role="status">
            <span className="loading-spinner" /> Loading ticket details…
          </div>
        ) : (
          <div className="ticket-drawer-content">
            <section className="drawer-ticket-intro">
              <div className="drawer-ticket-title-row">
                <h3>{current.title}</h3>
                <span className={`ticket-status-pill ticket-status-pill--${current.status.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
                  {current.status}
                </span>
              </div>
              <p>{current.description}</p>
              <div className="drawer-ticket-chips">
                <span className={`ticket-priority-pill ticket-priority-pill--${current.priority.toLowerCase()}`}>
                  {current.priority} priority
                </span>
                <span>{current.category} / {current.subcategory}</span>
              </div>
            </section>

            <div className="ticket-drawer-panels">
              <StatusUpdatePanel key={current.status} status={current.status} onSave={saveStatus} />
              <AssignmentPanel key={current.assigned_group} assignedGroup={current.assigned_group} onSave={saveAssignment} />
            </div>

            <section className="drawer-section" aria-labelledby="ticket-information-title">
              <div className="drawer-section-heading">
                <div>
                  <p className="ticket-eyebrow">RECORD</p>
                  <h3 id="ticket-information-title">Ticket information</h3>
                </div>
              </div>
              <dl className="drawer-info-grid">
                <div><dt>Issue</dt><dd>{current.title}</dd></div>
                <div><dt>Classification</dt><dd>{current.category} · {current.subcategory}</dd></div>
                <div><dt>Priority</dt><dd>{current.priority}</dd></div>
                <div><dt>Impact</dt><dd>{current.impact}</dd></div>
                <div><dt>Assigned group</dt><dd>{current.assigned_group}</dd></div>
                <div><dt>Status</dt><dd>{current.status}</dd></div>
                <div><dt>Created</dt><dd>{formatDate(current.created_at)}</dd></div>
                <div><dt>Last updated</dt><dd>{formatDate(current.updated_at)}</dd></div>
              </dl>
            </section>

            <section className="drawer-section" aria-labelledby="ticket-ai-recommendation-title">
              <div className="drawer-section-heading">
                <div>
                  <p className="ticket-eyebrow">AI ASSISTANCE</p>
                  <h3 id="ticket-ai-recommendation-title">AI recommendation</h3>
                </div>
              </div>
              <p className="drawer-body-copy">
                {current.ai_recommendation || 'No AI recommendation was recorded for this ticket.'}
              </p>
              {current.resolution && (
                <div className="drawer-resolution-note">
                  <strong>Resolution</strong>
                  <p>{current.resolution}</p>
                </div>
              )}
            </section>

            <section className="drawer-section" aria-labelledby="ticket-knowledge-title">
              <div className="drawer-section-heading">
                <div>
                  <p className="ticket-eyebrow">KNOWLEDGE BASE</p>
                  <h3 id="ticket-knowledge-title">Knowledge sources</h3>
                </div>
              </div>
              {current.knowledge_sources.length ? (
                <ul className="drawer-source-list">
                  {current.knowledge_sources.map((source) => <li key={source}>{source}</li>)}
                </ul>
              ) : (
                <p className="drawer-muted">No knowledge sources were attached to this ticket.</p>
              )}
            </section>

            <section className="drawer-section" aria-labelledby="ticket-similar-title">
              <div className="drawer-section-heading">
                <div>
                  <p className="ticket-eyebrow">RELATED WORK</p>
                  <h3 id="ticket-similar-title">Similar incidents</h3>
                </div>
              </div>
              {current.similar_incidents.length ? (
                <ul className="drawer-similar-list">
                  {current.similar_incidents.map((incident) => (
                    <li key={incident.ticket_id}>
                      <strong>{incident.ticket_number ?? incident.ticket_id}</strong>
                      <span>{incident.summary} · {incident.category} · {incident.priority}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="drawer-muted">No similar incidents were recorded for this ticket.</p>
              )}
            </section>

            <TicketComments comments={comments} onAdd={postComment} />
            <TicketHistory history={details?.history ?? []} />
          </div>
        )}
      </aside>
    </div>
  )
}
