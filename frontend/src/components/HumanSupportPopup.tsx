interface HumanSupportPopupProps {
  conversationId: string
  onClose: () => void
}

export function HumanSupportPopup({
  conversationId,
  onClose,
}: HumanSupportPopupProps) {
  return (
    <div className="handoff-confirmation-backdrop" role="presentation">
      <section
        className="handoff-confirmation"
        role="dialog"
        aria-modal="true"
        aria-labelledby="handoff-confirmation-title"
      >
        <button
          className="handoff-confirmation__close"
          type="button"
          aria-label="Close confirmation"
          onClick={onClose}
        >
          ×
        </button>
        <span className="handoff-confirmation__check" aria-hidden="true">✓</span>
        <h2 id="handoff-confirmation-title">Human Support Request Created</h2>
        <dl>
          <div><dt>Reference ID</dt><dd>{conversationId}</dd></div>
          <div><dt>Status</dt><dd>Waiting for Human Support Engineer</dd></div>
        </dl>
        <p>Your conversation has been shared with the support team.</p>
        <button className="handoff-confirmation__action" type="button" onClick={onClose}>
          Open human support chat
        </button>
      </section>
    </div>
  )
}
