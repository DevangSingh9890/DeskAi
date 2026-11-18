import { useState, type FormEvent } from 'react'

import { getTicketErrorMessage } from '../services/ticketService'
import type { TicketComment as TicketCommentType } from '../types/ticket'

interface TicketCommentsProps {
  comments: TicketCommentType[]
  onAdd: (body: string) => Promise<void>
}

function formatCommentDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function TicketComments({ comments, onAdd }: TicketCommentsProps) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = draft.trim()
    if (!body || isSaving) return

    setIsSaving(true)
    setError(null)
    try {
      await onAdd(body)
      setDraft('')
    } catch (submitError: unknown) {
      setError(getTicketErrorMessage(submitError))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="drawer-section ticket-comments" aria-labelledby="ticket-comments-title">
      <div className="drawer-section-heading">
        <div>
          <p className="ticket-eyebrow">COLLABORATION</p>
          <h3 id="ticket-comments-title">Comments</h3>
        </div>
        <span className="drawer-count">{comments.length}</span>
      </div>
      <div className="ticket-comment-list">
        {comments.length ? comments.map((comment) => (
          <article className="ticket-comment" key={comment.id}>
            <div className="timeline-avatar" aria-hidden="true">
              {comment.author.slice(0, 1).toUpperCase()}
            </div>
            <div className="ticket-comment-content">
              <div className="ticket-comment-meta">
                <strong>{comment.author}</strong>
                <time dateTime={comment.created_at}>{formatCommentDate(comment.created_at)}</time>
              </div>
              <p>{comment.body}</p>
            </div>
          </article>
        )) : (
          <p className="drawer-muted">No comments yet. Add the first update for this ticket.</p>
        )}
      </div>
      <form className="ticket-comment-form" onSubmit={(event) => void submitComment(event)}>
        <label className="sr-only" htmlFor="ticket-comment-input">Add a comment</label>
        <textarea
          id="ticket-comment-input"
          value={draft}
          maxLength={5000}
          rows={3}
          placeholder="Share an update with the service desk..."
          onChange={(event) => setDraft(event.target.value)}
        />
        {error && <p className="drawer-inline-error" role="alert">{error}</p>}
        <div className="ticket-comment-form-footer">
          <span>{draft.length}/5000</span>
          <button className="drawer-primary-button" type="submit" disabled={!draft.trim() || isSaving}>
            {isSaving ? 'Posting…' : 'Post comment'}
          </button>
        </div>
      </form>
    </section>
  )
}
