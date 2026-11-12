import type { FormEvent, KeyboardEvent } from 'react'

interface ChatInputProps {
  value: string
  isLoading: boolean
  isUploading: boolean
  uploadProgress: number
  uploadingFilename: string | null
  onChange: (value: string) => void
  onSubmit: () => void
  onAttach: (file: File) => void
}

export function ChatInput({
  value,
  isLoading,
  isUploading,
  uploadProgress,
  uploadingFilename,
  onChange,
  onSubmit,
  onAttach,
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
    <div className="composer-wrap">
      {isUploading && uploadingFilename && (
        <div className="composer-upload-progress" role="status" aria-live="polite">
          <span className="composer-upload-name" title={uploadingFilename}>
            <span className="composer-upload-spinner" aria-hidden="true" />
            Uploading {uploadingFilename}
          </span>
          <span>{uploadProgress}%</span>
          <div className="composer-progress-track">
            <span style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      )}
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
        <label
          className={`attach-button ${isUploading ? 'attach-button--disabled' : ''}`}
          htmlFor="chat-file-attachment"
          title="Upload a document to the knowledge base"
          aria-label="Upload a document to the knowledge base"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m9 12.5 5.7-5.7a3 3 0 0 1 4.2 4.2l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.5-8.5" />
          </svg>
        </label>
        <input
          className="sr-only"
          id="chat-file-attachment"
          type="file"
          accept=".pdf,.docx,.txt"
          disabled={isUploading}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) onAttach(file)
            event.target.value = ''
          }}
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
    </div>
  )
}
