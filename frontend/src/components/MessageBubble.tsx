import type { ChatMessage } from '../types/chat'

interface MessageBubbleProps {
  message: ChatMessage
}

function AssistantMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.8 13.8 9l6.2 1.8-6.2 1.8-1.8 6.2-1.8-6.2L4 10.8 10.2 9 12 2.8Z" />
      <path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z" />
    </svg>
  )
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isAssistant = message.role === 'assistant'

  return (
    <article
      className={`message-row ${isAssistant ? 'message-row--assistant' : 'message-row--user'}`}
    >
      {isAssistant && (
        <div className="message-avatar message-avatar--assistant">
          <AssistantMark />
        </div>
      )}
      <div className="message-content">
        <div className="message-meta">
          <span className="message-author">
            {isAssistant ? 'DeskAI Assistant' : 'You'}
          </span>
          <time
            className="message-time"
            dateTime={message.timestamp.toISOString()}
            title={message.timestamp.toLocaleString()}
          >
            {message.timestamp.toLocaleTimeString([], {
              hour: 'numeric',
              minute: '2-digit',
            })}
          </time>
        </div>
        <div className={`message-bubble ${isAssistant ? 'message-bubble--assistant' : 'message-bubble--user'}`}>
          {message.content}
        </div>
      </div>
      {!isAssistant && (
        <div className="message-avatar message-avatar--user" aria-hidden="true">
          Y
        </div>
      )}
    </article>
  )
}
