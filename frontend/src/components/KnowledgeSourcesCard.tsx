interface KnowledgeSourcesCardProps {
  sources?: string[] | null
}

export function KnowledgeSourcesCard({ sources }: KnowledgeSourcesCardProps) {
  const uniqueSources = [...new Set(sources?.filter((source) => source.trim()) ?? [])]
  if (!uniqueSources.length) return null

  return (
    <details className="agent-data-card" open>
      <summary className="agent-data-card-summary">
        <span className="agent-data-card-title">Knowledge References</span>
        <span className="agent-source-count">
          {uniqueSources.length} {uniqueSources.length === 1 ? 'reference' : 'references'}
        </span>
        <span className="agent-card-chevron" aria-hidden="true" />
      </summary>
      <div className="agent-data-card-content">
        <ul className="knowledge-source-list">
          {uniqueSources.map((source) => (
            <li key={source}>
              <span aria-hidden="true">📄</span>
              <span>{source}</span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}
