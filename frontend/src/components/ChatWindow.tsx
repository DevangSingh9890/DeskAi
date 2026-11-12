import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../types/chat'
import { ChatInput } from './ChatInput'
import { MessageBubble } from './MessageBubble'

interface ChatWindowProps {
  messages: ChatMessage[]
  draft: string
  isLoading: boolean
  error: string | null
  onDraftChange: (value: string) => void
  onSend: () => void
  onSelectSuggestion: (value: string) => void
}

const suggestions = [
  'I can’t connect to the VPN',
  'Help me reset my password',
  'My laptop is running slowly',
]

function TypingIndicator() {
  return (
    <div className="message-row message-row--assistant" aria-label="Assistant is typing">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M12 2.8 13.8 9l6.2 1.8-6.2 1.8-1.8 6.2-1.8-6.2L4 10.8 10.2 9 12 2.8Z" />
        </svg>
      </div>
      <div className="message-content">
        <div className="message-meta">
          <span className="message-author">DeskAI Assistant</span>
          <span className="message-time">Thinking</span>
        </div>
        <div className="typing-bubble" role="status">
          <span />
          <span />
          <span />
          <span className="sr-only">Assistant is preparing a response</span>
        </div>
      </div>
    </div>
  )
}

export function ChatWindow({
  messages,
  draft,
  isLoading,
  error,
  onDraftChange,
  onSend,
  onSelectSuggestion,
}: ChatWindowProps) {
  const endOfMessagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isLoading])

  return (
    <main className="chat-card" aria-label="Service desk chat">
      <div className="conversation-header">
        <div>
          <p className="conversation-eyebrow">YOUR IT SUPPORT</p>
          <h1>How can we help?</h1>
          <p className="conversation-description">
            Describe what’s going on and we’ll figure it out together.
          </p>
        </div>
        <div className="response-time">
          <span className="response-time-icon" aria-hidden="true">
            <svg viewBox="0 0 20 20">
              <circle cx="10" cy="10" r="7" />
              <path d="M10 6v4l2.5 1.5" />
            </svg>
          </span>
          Usually replies in seconds
        </div>
      </div>

      <section
        className="message-list"
        aria-label="Conversation"
        aria-live="polite"
        aria-relevant="additions"
      >
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {messages.length === 1 && !isLoading && (
          <div className="suggestions" aria-label="Suggested questions">
            <p>Here are a few things I can help with</p>
            <div className="suggestion-list">
              {suggestions.map((suggestion) => (
                <button
                  className="suggestion-chip"
                  key={suggestion}
                  type="button"
                  onClick={() => onSelectSuggestion(suggestion)}
                >
                  {suggestion}
                  <span aria-hidden="true">↗</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {isLoading && <TypingIndicator />}
        <div ref={endOfMessagesRef} />
      </section>

      <div className="composer-area">
        {error && (
          <div className="error-message" role="alert">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="10" cy="10" r="7" />
              <path d="M10 6.5v4M10 13.5h.01" />
            </svg>
            <span>{error}</span>
          </div>
        )}
        <ChatInput
          value={draft}
          isLoading={isLoading}
          onChange={onDraftChange}
          onSubmit={onSend}
        />
        <p className="privacy-note">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <rect x="3.5" y="7" width="9" height="7" rx="1.5" />
            <path d="M5.5 7V5a2 2 0 0 1 4 0v2" />
          </svg>
          Your conversation is only used to help resolve your request.
        </p>
      </div>
    </main>
  )
}
