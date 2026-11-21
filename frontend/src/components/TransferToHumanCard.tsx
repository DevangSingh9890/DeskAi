interface TransferToHumanCardProps {
  disabled: boolean
  error: string | null
  onTransfer: () => void
  onContinue: () => void
}

export function TransferToHumanCard({
  disabled,
  error,
  onTransfer,
  onContinue,
}: TransferToHumanCardProps) {
  return (
    <aside className="handoff-recommendation" aria-label="Human support recommendation">
      <div className="handoff-recommendation__icon" aria-hidden="true">?</div>
      <div className="handoff-recommendation__body">
        <strong>Would you like to transfer this conversation to a human support engineer?</strong>
        <div className="handoff-recommendation__actions">
          <button type="button" disabled={disabled} onClick={onTransfer}>
            {disabled ? 'Transferring…' : 'Transfer Chat'}
          </button>
          <button type="button" className="handoff-button--secondary" onClick={onContinue}>
            Continue With AI
          </button>
        </div>
        {error && <p className="handoff-error" role="alert">{error}</p>}
      </div>
    </aside>
  )
}
