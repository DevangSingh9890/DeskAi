import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  getHandoffErrorMessage,
  getHumanConversation,
  sendHumanMessage,
} from '../services/handoffService'
import type { HumanConversation, HumanChatMessage } from '../types/handoff'
import { formatServiceRequestId } from '../utils/handoff'

interface HumanChatWidgetProps {
  conversationId: string
  initiallyMinimized?: boolean
  onClosed: (conversationId: string) => void
}

export function HumanChatWidget({
  conversationId,
  initiallyMinimized = false,
  onClosed,
}: HumanChatWidgetProps) {
  const [conversation, setConversation] = useState<HumanConversation | null>(null)
  const [messages, setMessages] = useState<HumanChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [minimized, setMinimized] = useState(initiallyMinimized)
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)

  useEffect(() => {
    let active = true
    let terminal = false
    let timeoutId: number | undefined

    async function poll() {
      try {
        const detail = await getHumanConversation(conversationId)
        if (!active) return
        if (
          detail.conversation.status === 'Resolved' ||
          detail.conversation.status === 'Closed'
        ) {
          terminal = true
          onClosed(conversationId)
          return
        }
        setConversation(detail.conversation)
        setMessages((currentMessages) => {
          const unchanged =
            currentMessages.length === detail.messages.length &&
            currentMessages.every(
              (message, index) => message.id === detail.messages[index]?.id,
            )
          return unchanged ? currentMessages : detail.messages
        })
        setError(null)
      } catch (pollError: unknown) {
        if (active) setError(getHandoffErrorMessage(pollError))
      } finally {
        if (active && !terminal) {
          timeoutId = window.setTimeout(() => void poll(), 2000)
        }
      }
    }

    void poll()
    return () => {
      active = false
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [conversationId, onClosed])

  useEffect(() => {
    shouldAutoScrollRef.current = true
  }, [conversationId])

  const latestMessageId = messages[messages.length - 1]?.id

  useEffect(() => {
    const messagesContainer = messagesContainerRef.current
    if (!minimized && shouldAutoScrollRef.current && messagesContainer) {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [latestMessageId, minimized])

  function handleMessagesScroll() {
    const messagesContainer = messagesContainerRef.current
    if (!messagesContainer) return
    shouldAutoScrollRef.current =
      messagesContainer.scrollHeight -
        messagesContainer.scrollTop -
        messagesContainer.clientHeight <
      64
  }

  const displayId = conversation
    ? formatServiceRequestId(conversation.id)
    : 'Support request'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (
      !message ||
      isSending ||
      conversation?.status === 'Resolved' ||
      conversation?.status === 'Closed'
    ) return

    setIsSending(true)
    setError(null)
    try {
      await sendHumanMessage(conversationId, 'user', message)
      setDraft('')
      const detail = await getHumanConversation(conversationId)
      setMessages(detail.messages)
      setConversation(detail.conversation)
    } catch (sendError: unknown) {
      setError(getHandoffErrorMessage(sendError))
    } finally {
      setIsSending(false)
    }
  }

  if (minimized) {
    return (
      <button
        className="human-chat-launcher"
        type="button"
        onClick={() => setMinimized(false)}
        aria-label="Open human support chat"
      >
        <span aria-hidden="true">✦</span>
        <span>Support chat</span>
        <span className="human-chat-launcher__id">{displayId}</span>
      </button>
    )
  }

  return (
    <section className="human-chat-widget" aria-label="Human support chat">
      <header className="human-chat-widget__header">
        <div>
          <strong>Human Support</strong>
          <span>{conversation?.assigned_agent ?? 'Waiting for an engineer'}</span>
        </div>
        <button type="button" onClick={() => setMinimized(true)} aria-label="Minimize support chat">−</button>
      </header>
      <div className="human-chat-widget__status">
        <span className={`human-status-dot human-status-dot--${conversation?.status === 'Resolved' ? 'resolved' : 'active'}`} />
        {conversation?.status === 'Pending' || conversation?.status === 'Waiting'
          ? 'Waiting for Human Support Engineer'
          : conversation?.status ?? 'Connecting'}
        <small>{displayId}</small>
      </div>
      <div
        className="human-chat-widget__messages"
        ref={messagesContainerRef}
        onScroll={handleMessagesScroll}
        aria-live="polite"
      >
        {messages.map((message) => (
          <article
            className={`human-chat-message human-chat-message--${message.sender_type}`}
            key={message.id}
          >
            <span>{message.sender_type === 'agent' ? conversation?.assigned_agent ?? 'Support Engineer' : message.sender_type === 'system' ? 'System' : 'You'}</span>
            <p>{message.message}</p>
            <time dateTime={message.created_at}>
              {new Date(message.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
            </time>
          </article>
        ))}
      </div>
      {error && <p className="human-chat-widget__error" role="alert">{error}</p>}
      <form className="human-chat-widget__composer" onSubmit={(event) => void handleSubmit(event)}>
        <input
          aria-label="Message the support engineer"
          value={draft}
          maxLength={4000}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            conversation?.status === 'Resolved' || conversation?.status === 'Closed'
              ? 'Conversation closed'
              : 'Write a message…'
          }
          disabled={
            isSending ||
            conversation?.status === 'Resolved' ||
            conversation?.status === 'Closed'
          }
        />
        <button
          type="submit"
          disabled={
            !draft.trim() ||
            isSending ||
            conversation?.status === 'Resolved' ||
            conversation?.status === 'Closed'
          }
        >
          Send
        </button>
      </form>
    </section>
  )
}
