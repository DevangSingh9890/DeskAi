import type { DocumentSummary } from '../services/documentService'

interface DocumentListProps {
  documents: DocumentSummary[]
  isLoading: boolean
  deletingId: string | null
  onDelete: (documentId: string) => void
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function DocumentIcon({ filename }: { filename: string }) {
  const fileType = filename.split('.').pop()?.toLowerCase() ?? 'file'

  return (
    <span className={`document-type document-type--${fileType}`} aria-label={fileType.toUpperCase()}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 3.75h7l5 5v11.5H6z" />
        <path d="M13 3.75v5h5M9 13h6M9 16.5h6" />
      </svg>
    </span>
  )
}

export function DocumentList({
  documents,
  isLoading,
  deletingId,
  onDelete,
}: DocumentListProps) {
  return (
    <section className="document-list-section" aria-labelledby="document-list-title">
      <div className="sidebar-section-heading">
        <div>
          <h2 id="document-list-title">Uploaded documents</h2>
          <p>Available to your assistant</p>
        </div>
        <span className="document-count">{documents.length}</span>
      </div>

      {isLoading ? (
        <div className="sidebar-loading" role="status">
          <span className="loading-spinner" />
          Loading documents…
        </div>
      ) : documents.length ? (
        <ul className="document-list">
          {documents.map((document) => (
            <li className="document-card" key={document.id}>
              <DocumentIcon filename={document.filename} />
              <div className="document-details">
                <h3 title={document.filename}>{document.filename}</h3>
                <div className="document-meta">
                  <span>{formatFileSize(document.size)}</span>
                  <span className="document-meta-dot" aria-hidden="true" />
                  <time dateTime={document.uploaded_at}>
                    {new Date(document.uploaded_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </time>
                </div>
              </div>
              <button
                className="document-delete-button"
                type="button"
                onClick={() => onDelete(document.id)}
                disabled={deletingId !== null}
                aria-label={`Delete ${document.filename}`}
                title="Delete document"
              >
                {deletingId === document.id ? (
                  <span className="delete-spinner" aria-hidden="true" />
                ) : (
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M4.5 6h11M8 6V4.5h4V6m2.5 0-.6 9.5H6.1L5.5 6m2.8 2.5v4.5m3.4-4.5v4.5" />
                  </svg>
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="document-empty">
          <span className="empty-folder-icon" aria-hidden="true">
            <svg viewBox="0 0 40 40">
              <path d="M6 12.5h11l3 3h14v15H6zM6 16h28" />
            </svg>
          </span>
          <p>No documents yet</p>
          <span>Upload a guide to get started.</span>
        </div>
      )}
    </section>
  )
}
