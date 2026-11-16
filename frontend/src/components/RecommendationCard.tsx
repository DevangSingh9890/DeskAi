interface RecommendationCardProps {
  recommendedAction?: string | null
  followUpSuggestions?: string[] | null
  summary?: string | null
}

function hasText(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function RecommendationCard({
  recommendedAction,
  followUpSuggestions,
  summary,
}: RecommendationCardProps) {
  const followUps = followUpSuggestions?.filter((suggestion) => suggestion.trim()) ?? []
  if (!hasText(recommendedAction) && !followUps.length && !hasText(summary)) {
    return null
  }

  return (
    <details className="agent-data-card recommendation-card" open>
      <summary className="agent-data-card-summary">
        <span className="agent-data-card-title">Final AI Recommendation</span>
        <span className="agent-card-chevron" aria-hidden="true" />
      </summary>
      <div className="agent-data-card-content recommendation-content">
        {hasText(recommendedAction) && (
          <section>
            <h4>Recommended Action</h4>
            <p>{recommendedAction}</p>
          </section>
        )}
        {followUps.length > 0 && (
          <section>
            <h4>Follow-up Suggestions</h4>
            <ul>
              {followUps.map((suggestion, index) => (
                <li key={`${index}-${suggestion}`}>{suggestion}</li>
              ))}
            </ul>
          </section>
        )}
        {hasText(summary) && (
          <section>
            <h4>Summary</h4>
            <p>{summary}</p>
          </section>
        )}
      </div>
    </details>
  )
}
