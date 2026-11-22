import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  acceptHumanConversation,
  getHandoffErrorMessage,
  getHumanConversation,
  resolveHumanConversation,
  sendHumanMessage,
} from '../services/handoffService'
import type { HumanConversationDetail } from '../types/handoff'

interface HumanConversationChatProps {
  conversationId: string | null
  onUpdated: () => void
}

function contextValue(context: Record<string, unknown>, key: string): unknown {
  return context[key]
}

export function HumanConversationChat({
  conversationId,
  onUpdated,
}: HumanConversationChatProps) {
  const [detail, setDetail] = useState<HumanConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!conversationId) {
      return
    }
    const id = conversationId
    let active = true
    let timeoutId: number | undefined
    async function poll() {
      try {
        const result = await getHumanConversation(id)
        if (active) {
          setDetail(result)
          setError(null)
        }
      } catch (pollError: unknown) {
        if (active) setError(getHandoffErrorMessage(pollError))
      } finally {
        if (active) timeoutId = window.setTimeout(() => void poll(), 2000)
      }
    }
    void poll()
    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [conversationId])

  if (!conversationId) {
    return <section className="human-conversation-empty">Select a conversation to view its history.</section>
  }
  const activeConversationId = conversationId

  async function handleAccept() {
    setBusy(true)
    setError(null)
    try {
      await acceptHumanConversation(activeConversationId, 'Support Engineer')
      onUpdated()
      setDetail(await getHumanConversation(activeConversationId))
    } catch (acceptError: unknown) {
      setError(getHandoffErrorMessage(acceptError))
    } finally {
      setBusy(false)
    }
  }

  async function handleResolve() {
    setBusy(true)
    setError(null)
    try {
      await resolveHumanConversation(activeConversationId)
      onUpdated()
      setDetail(await getHumanConversation(activeConversationId))
    } catch (resolveError: unknown) {
      setError(getHandoffErrorMessage(resolveError))
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (!message || busy) return
    setBusy(true)
    setError(null)
    try {
      await sendHumanMessage(activeConversationId, 'agent', message)
      setDraft('')
      setDetail(await getHumanConversation(activeConversationId))
    } catch (sendError: unknown) {
      setError(getHandoffErrorMessage(sendError))
    } finally {
      setBusy(false)
    }
  }

  const conversation = detail?.conversation
  const ticketData = conversation ? contextValue(conversation.context, 'ticket_data') : null
  const classification = conversation ? contextValue(conversation.context, 'classification') : null
  const knowledgeSources = conversation ? contextValue(conversation.context, 'knowledge_sources') : null

  return (
    <section className="human-conversation-chat" aria-label="Human support chat window">
      <div className="human-conversation-chat__main">
        <header className="human-conversation-chat__header">
          <div>
            <p className="ticket-eyebrow">HUMAN SUPPORT</p>
            <h3>{conversation?.conversation_id ?? conversationId}</h3>
            <p>{conversation?.category ?? 'Loading'} · {conversation?.priority ?? '—'} priority · {conversation?.status ?? ''}</p>
          </div>
          {conversation?.status === 'Pending' || conversation?.status === 'Waiting' ? (
            <button type="button" disabled={busy} onClick={() => void handleAccept()}>
              {busy ? 'Accepting…' : 'Accept Conversation'}
            </button>
          ) : conversation &&
            conversation.status !== 'Resolved' &&
            conversation.status !== 'Closed' ? (
            <button className="human-resolve-button" type="button" disabled={busy} onClick={() => void handleResolve()}>
              Resolve
            </button>
          ) : null}
        </header>
        {error && <p className="human-admin-error" role="alert">{error}</p>}
        <div className="human-conversation-history">
          {detail?.messages.map((message) => (
            <article className={`human-admin-message human-admin-message--${message.sender_type}`} key={message.id}>
              <div><strong>{message.sender_type === 'agent' ? conversation?.assigned_agent ?? 'Support Engineer' : message.sender_type === 'system' ? 'System' : 'User'}</strong><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString()}</time></div>
              <p>{message.message}</p>
            </article>
          ))}
          {!detail && <p className="human-queue-empty">Loading conversation…</p>}
        </div>
        {conversation?.status !== 'Resolved' &&
          conversation?.status !== 'Closed' &&
          conversation?.status !== 'Pending' &&
          conversation?.status !== 'Waiting' && (
            <form className="human-admin-composer" onSubmit={(event) => void handleSubmit(event)}>
              <input
                aria-label="Reply to user"
                placeholder="Write a reply…"
                value={draft}
                maxLength={4000}
                onChange={(event) => setDraft(event.target.value)}
              />
              <button type="submit" disabled={!draft.trim() || busy}>Send reply</button>
            </form>
          )}
      </div>
      <aside className="human-conversation-context" aria-label="Ticket details and AI context">
        <header className="human-conversation-context__header">
          <div>
            <p className="ticket-eyebrow">CASE OVERVIEW</p>
            <h4>Ticket details</h4>
          </div>
          {conversation && (
            <span className={`human-status-label human-status-label--${conversation.status.toLowerCase().replace(' ', '-')}`}>
              {conversation.status === 'Waiting' ? 'Pending' : conversation.status}
            </span>
          )}
        </header>
        <section className="human-context-group">
          <h5>Ticket &amp; transfer</h5>
          <dl>
            <div><dt>Ticket</dt><dd>{conversation?.ticket_id ?? 'No linked ticket'}</dd></div>
            <div><dt>Category</dt><dd>{conversation?.category ?? '—'}</dd></div>
            <div><dt>Priority</dt><dd>{conversation?.priority ?? '—'}</dd></div>
            <div><dt>Assigned to</dt><dd>{conversation?.assigned_agent ?? 'Unassigned'}</dd></div>
            <div><dt>Received</dt><dd>{conversation ? new Date(conversation.created_at).toLocaleString() : '—'}</dd></div>
          </dl>
        </section>
        <section className="human-context-group">
          <h5>AI context</h5>
          <dl>
            <div>
              <dt>AI summary</dt>
              <dd>
                {typeof conversation?.context.summary === 'string'
                  ? conversation.context.summary
                  : conversation?.context.summary
                    ? JSON.stringify(conversation.context.summary)
                    : 'No summary available'}
              </dd>
            </div>
            <div><dt>Classification</dt><dd>{classification ? JSON.stringify(classification) : 'Not available'}</dd></div>
            <div><dt>Knowledge sources</dt><dd>{Array.isArray(knowledgeSources) && knowledgeSources.length ? knowledgeSources.join(', ') : 'None retrieved'}</dd></div>
            <div><dt>Knowledge results</dt><dd>
              {Array.isArray(conversation?.context.knowledge_results)
                ? `${conversation.context.knowledge_results.length} retrieved result(s)`
                : 'No retrieved results'}
            </dd></div>
            <div><dt>Ticket information</dt><dd>{ticketData ? JSON.stringify(ticketData) : 'No ticket data'}</dd></div>
          </dl>
        </section>
        {conversation && Boolean(conversation.context.conversation_history) && (
          <details>
            <summary>Full AI conversation snapshot</summary>
            <pre>{JSON.stringify(conversation.context.conversation_history, null, 2)}</pre>
          </details>
        )}
        {conversation && Boolean(conversation.context.knowledge_results) && (
          <details>
            <summary>Knowledge search results</summary>
            <pre>{JSON.stringify(conversation.context.knowledge_results, null, 2)}</pre>
          </details>
        )}
      </aside>
    </section>
  )
}
