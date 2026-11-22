import { useState } from 'react'
import type { HumanConversationStatus, HumanConversationSummary } from '../types/handoff'

interface HumanConversationListProps {
  conversations: HumanConversationSummary[]
  selectedId: string | null
  filter: ConversationFilter
  onFilterChange: (filter: ConversationFilter) => void
  onSelect: (conversationId: string) => void
}

type ConversationFilter =
  | 'All'
  | Exclude<HumanConversationStatus, 'Waiting'>

const filters: ConversationFilter[] = [
  'All',
  'Pending',
  'Assigned',
  'In Progress',
  'Resolved',
  'Closed',
]

export function HumanConversationList({
  conversations,
  selectedId,
  filter,
  onFilterChange,
  onSelect,
}: HumanConversationListProps) {
  const [query, setQuery] = useState('')
  const filtered = filter === 'All'
    ? conversations
    : conversations.filter((conversation) =>
        filter === 'Pending'
          ? conversation.status === 'Pending' || conversation.status === 'Waiting'
          : conversation.status === filter,
      )
  const search = query.trim().toLowerCase()
  const visible = search
    ? filtered.filter((conversation) =>
        [
          conversation.conversation_id,
          conversation.ticket_id,
          conversation.category,
          conversation.priority,
          conversation.status,
        ].some((value) => value?.toLowerCase().includes(search)),
      )
    : filtered

  return (
    <section className="human-queue-list" aria-label="Human support conversations">
      <label className="human-queue-search">
        <span className="sr-only">Search conversations</span>
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="m13 13 4 4" />
        </svg>
        <input
          type="search"
          placeholder="Search conversations"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className="human-queue-list__filters" aria-label="Filter support queue">
        {filters.map((value) => (
          <button
            key={value}
            className={filter === value ? 'human-queue-filter human-queue-filter--active' : 'human-queue-filter'}
            type="button"
            onClick={() => onFilterChange(value)}
          >
            {value === 'In Progress' ? 'Active' : value}
            {value !== 'All' && (
              <span>
                {conversations.filter((conversation) =>
                  value === 'Pending'
                    ? conversation.status === 'Pending' || conversation.status === 'Waiting'
                    : conversation.status === value,
                ).length}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="human-queue-list__rows">
        {visible.length === 0 ? (
          <p className="human-queue-empty">No conversations in this queue.</p>
        ) : visible.map((conversation) => (
          <button
            className={selectedId === conversation.conversation_id ? 'human-queue-row human-queue-row--selected' : 'human-queue-row'}
            type="button"
            key={conversation.conversation_id}
            onClick={() => onSelect(conversation.conversation_id)}
          >
            <span className="human-queue-row__top">
              <strong>{conversation.conversation_id}</strong>
              <span className={`human-status-label human-status-label--${conversation.status.toLowerCase().replace(' ', '-')}`}>
                {conversation.status === 'Waiting' ? 'Pending' : conversation.status}
              </span>
            </span>
            <span className="human-queue-row__details">
              <span>{conversation.category}</span>
              <span className={`human-priority human-priority--${conversation.priority.toLowerCase()}`}>
                <span aria-hidden="true">●</span> {conversation.priority}
              </span>
            </span>
            <time dateTime={conversation.created_at}>{new Date(conversation.created_at).toLocaleString()}</time>
          </button>
        ))}
      </div>
    </section>
  )
}
