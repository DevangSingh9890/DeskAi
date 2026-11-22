import { useEffect, useState } from 'react'
import {
  getHandoffErrorMessage,
  getHumanConversations,
} from '../services/handoffService'
import type { HumanConversationStatus, HumanConversationSummary } from '../types/handoff'
import { HumanConversationChat } from './HumanConversationChat'
import { HumanConversationList } from './HumanConversationList'

export function HumanSupportQueue() {
  const [conversations, setConversations] = useState<HumanConversationSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<
    'All' | Exclude<HumanConversationStatus, 'Waiting'>
  >('All')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let timeoutId: number | undefined
    async function poll() {
      try {
        const result = await getHumanConversations()
        if (!active) return
        setConversations(result)
        setError(null)
        setSelectedId((current) =>
          current && result.some((conversation) => conversation.conversation_id === current)
            ? current
            : result[0]?.conversation_id ?? null,
        )
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
  }, [])

  function handleUpdated() {
    void getHumanConversations()
      .then(setConversations)
      .catch((updateError: unknown) => setError(getHandoffErrorMessage(updateError)))
  }

  const counts = {
    pending: conversations.filter(
      (conversation) =>
        conversation.status === 'Pending' || conversation.status === 'Waiting',
    ).length,
    assigned: conversations.filter((conversation) => conversation.status === 'Assigned').length,
    active: conversations.filter((conversation) => conversation.status === 'In Progress').length,
    resolved: conversations.filter((conversation) => conversation.status === 'Resolved').length,
    closed: conversations.filter((conversation) => conversation.status === 'Closed').length,
  }

  return (
    <section className="human-support-queue" aria-labelledby="human-support-title">
      <header className="human-support-queue__header">
        <div>
          <p className="ticket-eyebrow">SERVICE OPERATIONS</p>
          <h2 id="human-support-title">Human Support Queue</h2>
        </div>
        <span className="human-queue-refresh"><span /> Polling every 2 seconds</span>
      </header>
      <div className="human-queue-summary">
        <div><span>Pending</span><strong>{counts.pending}</strong></div>
        <div><span>Assigned</span><strong>{counts.assigned}</strong></div>
        <div><span>Active</span><strong>{counts.active}</strong></div>
        <div><span>Resolved</span><strong>{counts.resolved}</strong></div>
        <div><span>Closed</span><strong>{counts.closed}</strong></div>
      </div>
      {error && <p className="human-admin-error" role="alert">{error}</p>}
      <div className="human-support-queue__workspace">
        <HumanConversationList
          conversations={conversations}
          selectedId={selectedId}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={setSelectedId}
        />
        <HumanConversationChat conversationId={selectedId} onUpdated={handleUpdated} />
      </div>
    </section>
  )
}
