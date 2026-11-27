import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getHandoffErrorMessage,
  getHumanConversation,
  getHumanConversations,
} from '../services/handoffService'
import type {
  HumanChatMessage,
  HumanConversationStatus,
  HumanConversationSummary,
} from '../types/handoff'
import { formatServiceRequestId } from '../utils/handoff'
import { HumanConversationChat } from './HumanConversationChat'
import { HumanConversationList } from './HumanConversationList'

export function HumanSupportQueue() {
  const [conversations, setConversations] = useState<HumanConversationSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<
    'All' | Exclude<HumanConversationStatus, 'Waiting'>
  >('All')
  const [error, setError] = useState<string | null>(null)
  const [lastViewedAt, setLastViewedAt] = useState<Record<string, string>>({})
  const [lastMessagePreview, setLastMessagePreview] = useState<Record<string, string>>({})
  const initializedActivity = useRef(false)
  const selectedIdRef = useRef<string | null>(null)
  const previewLoadedIds = useRef(new Set<string>())

  const handleMessagesLoaded = useCallback(
    (conversationId: string, messages: HumanChatMessage[]) => {
      const latestMessage = messages[messages.length - 1]?.message
      if (!latestMessage) return
      setLastMessagePreview((current) =>
        current[conversationId] === latestMessage
          ? current
          : { ...current, [conversationId]: latestMessage },
      )
    },
    [],
  )

  useEffect(() => {
    let active = true
    let timeoutId: number | undefined
    async function poll() {
      try {
        const result = await getHumanConversations()
        if (!active) return
        setConversations(result)
        setError(null)
        const selectedId =
          selectedIdRef.current &&
          result.some(
            (conversation) =>
              conversation.conversation_id === selectedIdRef.current,
          )
            ? selectedIdRef.current
            : result[0]?.conversation_id ?? null
        selectedIdRef.current = selectedId
        setSelectedId(selectedId)
        for (const conversation of result) {
          if (previewLoadedIds.current.has(conversation.conversation_id)) continue
          previewLoadedIds.current.add(conversation.conversation_id)
          if (conversation.conversation_id === selectedId) continue
          void getHumanConversation(conversation.conversation_id)
            .then((detail) => {
              if (active) {
                handleMessagesLoaded(conversation.conversation_id, detail.messages)
              }
            })
            .catch((previewError: unknown) => {
              if (!active) return
              setLastMessagePreview((current) => ({
                ...current,
                [conversation.conversation_id]: 'Preview unavailable',
              }))
              setError(getHandoffErrorMessage(previewError))
            })
        }
        const firstLoad = !initializedActivity.current
        setLastViewedAt((current) => {
          let next = current
          for (const conversation of result) {
            if (
              firstLoad ||
              conversation.conversation_id === selectedIdRef.current
            ) {
              if (next[conversation.conversation_id] !== conversation.updated_at) {
                if (next === current) next = { ...current }
                next[conversation.conversation_id] = conversation.updated_at
              }
            }
          }
          return next
        })
        initializedActivity.current = true
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
  }, [handleMessagesLoaded])

  function handleSelect(conversationId: string) {
    selectedIdRef.current = conversationId
    setSelectedId(conversationId)
    const selected = conversations.find(
      (conversation) => conversation.conversation_id === conversationId,
    )
    if (selected) {
      setLastViewedAt((current) =>
        current[conversationId] === selected.updated_at
          ? current
          : { ...current, [conversationId]: selected.updated_at },
      )
    }
  }

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
  const displayIdByConversationId = new Map(
    conversations.map((conversation) => [
      conversation.conversation_id,
      formatServiceRequestId(conversation.id),
    ]),
  )
  const unreadIds = new Set(
    conversations
      .filter((conversation) => {
        const viewedAt = lastViewedAt[conversation.conversation_id]
        return (
          !viewedAt ||
          Date.parse(conversation.updated_at) > Date.parse(viewedAt)
        )
      })
      .map((conversation) => conversation.conversation_id),
  )

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
          displayIdByConversationId={displayIdByConversationId}
          unreadIds={unreadIds}
          lastMessagePreview={lastMessagePreview}
          filter={filter}
          onFilterChange={setFilter}
          onSelect={handleSelect}
        />
        <HumanConversationChat
          conversationId={selectedId}
          displayId={selectedId ? displayIdByConversationId.get(selectedId) ?? '' : ''}
          onMessagesLoaded={handleMessagesLoaded}
          onUpdated={handleUpdated}
        />
      </div>
    </section>
  )
}
