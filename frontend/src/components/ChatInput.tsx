import type { FormEvent, KeyboardEvent } from 'react'

interface ChatInputProps {
  value: string
  isLoading: boolean
  onChange: (value: string) => void
  onSubmit: () => void
}

export function ChatInput({
  value,
  isLoading,
  onChange,
  onSubmit,
}: ChatInputProps) {
  const canSend = value.trim().length > 0 && !isLoading

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (canSend) onSubmit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      if (canSend) onSubmit()
    }
  }

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <label className="sr-only" htmlFor="chat-message">
        Write a message
      </label>
      <textarea
        id="chat-message"
        className="chat-textarea"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe the issue you're experiencing..."
        rows={1}
        maxLength={4000}
        disabled={isLoading}
      />
      <button
        className="send-button"
        type="submit"
        disabled={!canSend}
        aria-label={isLoading ? 'Sending message' : 'Send message'}
      >
        {isLoading ? (
          <span className="send-spinner" aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4.5 12 20 4.5l-4.8 15-3.1-6.3L4.5 12Z" />
            <path d="m12.1 13.2 4.1-4.1" />
          </svg>
        )}
      </button>
      <p className="input-hint">
        Press <kbd>Enter</kbd> to send <span aria-hidden="true">·</span>{' '}
        <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line
      </p>
    </form>
  )
}
