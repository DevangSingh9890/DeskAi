interface SatisfactionWidgetProps {
  onFeedback: (helpful: boolean) => void
}

export function SatisfactionWidget({ onFeedback }: SatisfactionWidgetProps) {
  return (
    <section className="satisfaction-widget" aria-label="Answer feedback">
      <span>Was this answer helpful?</span>
      <button
        type="button"
        aria-label="Yes, this answer was helpful"
        onClick={() => onFeedback(true)}
      >
        👍 Yes
      </button>
      <button
        type="button"
        aria-label="No, this answer was not helpful"
        onClick={() => onFeedback(false)}
      >
        👎 No
      </button>
    </section>
  )
}
