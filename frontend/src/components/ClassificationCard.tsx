import type { AgentClassification } from '../types/chat'

interface ClassificationCardProps {
  classification?: AgentClassification | null
}

function hasValue(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function ClassificationCard({
  classification,
}: ClassificationCardProps) {
  if (!classification) return null

  const confidence =
    typeof classification.confidence === 'number'
      ? classification.confidence
      : classification.confidence_score
  const details = [
    ['Issue', classification.issue],
    ['Subcategory', classification.subcategory],
    ['Impact', classification.impact],
    ['Assigned Group', classification.assigned_group],
  ].filter(([, value]) => hasValue(value))

  if (
    !details.length &&
    !hasValue(classification.category) &&
    !hasValue(classification.priority) &&
    typeof confidence !== 'number'
  ) {
    return null
  }

  const priorityClass = classification.priority
    ?.toLowerCase()
    .replace(/[^a-z]+/g, '-')

  return (
    <details className="agent-data-card" open>
      <summary className="agent-data-card-summary">
        <span className="agent-data-card-title">Issue Classification</span>
        <span className="agent-card-chevron" aria-hidden="true" />
      </summary>
      <div className="agent-data-card-content">
        <div className="classification-badges">
          {hasValue(classification.category) && (
            <span className="classification-badge classification-badge--category">
              {classification.category}
            </span>
          )}
          {hasValue(classification.priority) && (
            <span
              className={`classification-badge classification-badge--priority classification-badge--${priorityClass}`}
            >
              {classification.priority} priority
            </span>
          )}
        </div>
        <dl className="classification-fields">
          {details.map(([label, value]) => (
            <div className="classification-field" key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
          {typeof confidence === 'number' && Number.isFinite(confidence) && (
            <div className="classification-field">
              <dt>Confidence Score</dt>
              <dd>{Math.round(confidence * 100)}%</dd>
            </div>
          )}
        </dl>
      </div>
    </details>
  )
}
