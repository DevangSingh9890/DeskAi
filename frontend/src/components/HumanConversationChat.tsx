import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import {
  acceptHumanConversation,
  getHandoffErrorMessage,
  getHumanConversation,
  resolveHumanConversation,
  sendHumanMessage,
} from '../services/handoffService'
import type { HumanChatMessage, HumanConversationDetail } from '../types/handoff'

interface HumanConversationChatProps {
  conversationId: string | null
  displayId: string
  onMessagesLoaded: (conversationId: string, messages: HumanChatMessage[]) => void
  onUpdated: () => void
}

function contextValue(context: Record<string, unknown>, key: string): unknown {
  return context[key]
}

function formatContextValue(value: unknown, fallback: string): string {
  if (typeof value === 'string') return value || fallback
  if (value === null || value === undefined) return fallback
  if (Array.isArray(value)) {
    const items = value
      .map((item) => formatContextValue(item, ''))
      .filter(Boolean)
    return items.length ? items.join('\n') : fallback
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value).map(
      ([key, item]) =>
        `${key.replace(/_/g, ' ')}: ${formatContextValue(item, '—')}`,
    )
    return entries.length ? entries.join('\n') : fallback
  }
  return String(value)
}

export function HumanConversationChat({
  conversationId,
  displayId,
  onMessagesLoaded,
  onUpdated,
}: HumanConversationChatProps) {
  const [detail, setDetail] = useState<HumanConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mobileContextConversationId, setMobileContextConversationId] = useState<string | null>(null)
  const historyRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const shouldAutoScroll = useRef(true)
  const pendingMessages = useRef(new Map<string, HumanChatMessage[]>())

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
          const pending = pendingMessages.current.get(id) ?? []
          const serverMessageIds = new Set(result.messages.map((message) => message.id))
          const unsynced = pending.filter((message) => !serverMessageIds.has(message.id))
          pendingMessages.current.set(id, unsynced)
          const messages = [...result.messages, ...unsynced].sort(
            (left, right) =>
              Date.parse(left.created_at) - Date.parse(right.created_at) ||
              left.id - right.id,
          )
          setDetail({ ...result, messages })
          onMessagesLoaded(id, messages)
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
  }, [conversationId, onMessagesLoaded])

  useEffect(() => {
    shouldAutoScroll.current = true
  }, [conversationId])

  const currentDetail =
    detail?.conversation.conversation_id === conversationId ? detail : null
  const messages = currentDetail?.messages ?? []
  const latestMessageId = messages[messages.length - 1]?.id

  useEffect(() => {
    if (shouldAutoScroll.current) {
      endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [conversationId, latestMessageId])

  if (!conversationId) {
    return <section className="human-conversation-empty">Select a conversation to view its history.</section>
  }
  const activeConversationId = conversationId
  const showMobileContext = mobileContextConversationId === activeConversationId

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
      const sentMessage = await sendHumanMessage(activeConversationId, 'agent', message)
      const pending = pendingMessages.current.get(activeConversationId) ?? []
      pendingMessages.current.set(activeConversationId, [...pending, sentMessage])
      setDetail((current) => {
        if (!current || current.conversation.conversation_id !== activeConversationId) {
          return current
        }
        return current.messages.some((item) => item.id === sentMessage.id)
          ? current
          : { ...current, messages: [...current.messages, sentMessage] }
      })
      onMessagesLoaded(activeConversationId, [sentMessage])
      setDraft('')
      onUpdated()
    } catch (sendError: unknown) {
      setError(getHandoffErrorMessage(sendError))
    } finally {
      setBusy(false)
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function handleHistoryScroll() {
    const history = historyRef.current
    if (!history) return
    shouldAutoScroll.current =
      history.scrollHeight - history.scrollTop - history.clientHeight < 80
  }

  const conversation = currentDetail?.conversation
  const ticketData = conversation ? contextValue(conversation.context, 'ticket_data') : null
  const classification = conversation ? contextValue(conversation.context, 'classification') : null
  const knowledgeSources = conversation ? contextValue(conversation.context, 'knowledge_sources') : null
  const troubleshooting = conversation
    ? contextValue(conversation.context, 'troubleshooting')
    : null
  const initialHistoryEnd = messages.findIndex(
    (message) =>
      message.sender_type === 'system' &&
      message.message.startsWith('Human support request created.'),
  )
  const renderedMessages = messages.map((message, index) => {
    const role =
      message.sender_type === 'agent' &&
      initialHistoryEnd !== -1 &&
      index < initialHistoryEnd
        ? 'ai'
        : message.sender_type
    const previousMessage = messages[index - 1]
    const previousRole =
      previousMessage?.sender_type === 'agent' &&
      initialHistoryEnd !== -1 &&
      index - 1 < initialHistoryEnd
        ? 'ai'
        : previousMessage?.sender_type
    const closeTogether =
      previousMessage &&
      Date.parse(message.created_at) - Date.parse(previousMessage.created_at) < 5 * 60 * 1000

    return {
      message,
      role,
      grouped: role === previousRole && closeTogether,
    }
  })

  return (
    <section className="human-conversation-chat" aria-label="Human support chat window">
      <div className="human-conversation-chat__main">
        <header className="human-conversation-chat__header">
          <div>
            <p className="ticket-eyebrow">HUMAN SUPPORT</p>
            <h3>{displayId}</h3>
            <p>
              {conversation?.category ?? 'Loading'} · {conversation?.priority ?? '—'} priority ·{' '}
              {conversation?.status ?? 'Loading status'}
              {' · '}Assigned to {conversation?.assigned_agent ?? '—'}
            </p>
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
          <button
            className="human-conversation-chat__context-toggle"
            type="button"
            aria-expanded={showMobileContext}
            onClick={() =>
              setMobileContextConversationId((current) =>
                current === activeConversationId ? null : activeConversationId,
              )
            }
          >
            {showMobileContext ? 'Hide details' : 'Case details'}
          </button>
        </header>
        {error && <p className="human-admin-error" role="alert">{error}</p>}
        <div
          className="human-conversation-history"
          ref={historyRef}
          onScroll={handleHistoryScroll}
          aria-live="polite"
        >
          {renderedMessages.map(({ message, role, grouped }) => (
            <article
              className={`human-admin-message human-admin-message--${role}${grouped ? ' human-admin-message--grouped' : ''}`}
              key={message.id}
            >
              <div className="human-admin-message__byline">
                <strong>
                  {role === 'ai'
                    ? 'DeskAI Assistant'
                    : role === 'agent'
                      ? conversation?.assigned_agent ?? 'Support Engineer'
                      : role === 'system'
                        ? 'System'
                        : 'User'}
                </strong>
                <time
                  dateTime={message.created_at}
                  title={new Date(message.created_at).toLocaleString()}
                >
                  {new Date(message.created_at).toLocaleTimeString([], {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </time>
              </div>
              <p>{message.message}</p>
            </article>
          ))}
          {!currentDetail && <p className="human-queue-empty">Loading conversation…</p>}
          <div ref={endRef} />
        </div>
        {conversation &&
          conversation.status !== 'Resolved' &&
          conversation.status !== 'Closed' &&
          conversation.status !== 'Pending' &&
          conversation.status !== 'Waiting' && (
            <form className="human-admin-composer" onSubmit={(event) => void handleSubmit(event)}>
              <textarea
                aria-label="Reply to user"
                placeholder="Write a reply…"
                value={draft}
                maxLength={4000}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                rows={2}
                disabled={busy}
              />
              <button type="submit" disabled={!draft.trim() || busy}>
                {busy ? 'Sending…' : 'Send reply'}
              </button>
              <span className="human-admin-composer__hint">Enter to send · Shift + Enter for a new line</span>
            </form>
          )}
      </div>
      <aside
        className={`human-conversation-context${showMobileContext ? ' human-conversation-context--mobile-open' : ''}`}
        aria-label="Case details and insights"
      >
        <header className="human-conversation-context__header">
          <div>
            <p className="ticket-eyebrow">CASE OVERVIEW</p>
            <h4>Current case</h4>
          </div>
          {conversation && (
            <span className={`human-status-label human-status-label--${conversation.status.toLowerCase().replace(' ', '-')}`}>
              {conversation.status === 'Waiting' ? 'Pending' : conversation.status}
            </span>
          )}
        </header>
        <section className="human-context-group">
          <h5>Case &amp; transfer</h5>
          <dl>
            <div><dt>SR Number</dt><dd>{displayId}</dd></div>
            <div><dt>Ticket ID</dt><dd>{conversation?.ticket_id ?? 'No linked ticket'}</dd></div>
            <div><dt>Category</dt><dd>{conversation?.category ?? '—'}</dd></div>
            <div><dt>Priority</dt><dd>{conversation?.priority ?? '—'}</dd></div>
            <div><dt>Status</dt><dd>{conversation?.status ?? '—'}</dd></div>
            <div><dt>Assigned to</dt><dd>{conversation?.assigned_agent ?? 'Unassigned'}</dd></div>
            <div><dt>Created</dt><dd>{conversation ? new Date(conversation.created_at).toLocaleString() : '—'}</dd></div>
            <div><dt>Last updated</dt><dd>{conversation ? new Date(conversation.updated_at).toLocaleString() : '—'}</dd></div>
          </dl>
        </section>
        <section className="human-context-group">
          <h5>Case insights</h5>
          <dl>
            <div>
              <dt>Summary</dt>
              <dd>
                {formatContextValue(conversation?.context.summary, 'No summary available')}
              </dd>
            </div>
            <div><dt>Classification</dt><dd>{formatContextValue(classification, 'Not available')}</dd></div>
            <div><dt>Knowledge references</dt><dd>{Array.isArray(knowledgeSources) && knowledgeSources.length ? knowledgeSources.join(', ') : 'None retrieved'}</dd></div>
            <div><dt>Search results</dt><dd>
              {Array.isArray(conversation?.context.knowledge_results)
                ? `${conversation.context.knowledge_results.length} retrieved result(s)`
                : 'No retrieved results'}
            </dd></div>
            <div><dt>Troubleshooting</dt><dd>{formatContextValue(troubleshooting, 'No troubleshooting summary')}</dd></div>
            <div><dt>Case status</dt><dd>{formatContextValue(ticketData, 'No ticket data')}</dd></div>
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
