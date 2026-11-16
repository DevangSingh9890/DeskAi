import type { AgentTroubleshooting } from '../types/chat'

interface TroubleshootingCardProps {
  troubleshooting?: AgentTroubleshooting | null
}

function hasText(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function TroubleshootingCard({
  troubleshooting,
}: TroubleshootingCardProps) {
  if (!troubleshooting) return null

  const steps =
    troubleshooting.troubleshooting_steps?.filter((step) => step.trim()) ?? []
  const hasContent =
    hasText(troubleshooting.likely_cause) ||
    steps.length > 0 ||
    hasText(troubleshooting.escalation_recommendation)

  if (!hasContent) return null

  return (
    <details className="agent-data-card" open>
      <summary className="agent-data-card-summary">
        <span className="agent-data-card-title">Troubleshooting</span>
        <span className="agent-card-chevron" aria-hidden="true" />
      </summary>
      <div className="agent-data-card-content troubleshooting-content">
        {hasText(troubleshooting.likely_cause) && (
          <section>
            <h4>Likely Cause</h4>
            <p>{troubleshooting.likely_cause}</p>
          </section>
        )}
        {steps.length > 0 && (
          <section>
            <h4>Troubleshooting Steps</h4>
            <ol>
              {steps.map((step, index) => (
                <li key={`${index}-${step}`}>{step}</li>
              ))}
            </ol>
          </section>
        )}
        {hasText(troubleshooting.escalation_recommendation) && (
          <section>
            <h4>Escalation Recommendation</h4>
            <p>{troubleshooting.escalation_recommendation}</p>
          </section>
        )}
      </div>
    </details>
  )
}
