import type { DocumentSummary } from '../services/documentService'

interface DocumentCardProps {
  document: DocumentSummary
  isDeleting: boolean
  onDelete: (documentId: string) => void
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatFileType(filename: string): string {
  const extension = filename.split('.').pop()?.toUpperCase()
  return extension || 'FILE'
}

export function DocumentCard({
  document,
  isDeleting,
  onDelete,
}: DocumentCardProps) {
  return (
    <article className="document-card">
      <div className={`document-type document-type--${formatFileType(document.filename).toLowerCase()}`}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 3.75h7l5 5v11.5H6z" />
          <path d="M13 3.75v5h5M9 13h6M9 16.5h6" />
        </svg>
        <span>{formatFileType(document.filename)}</span>
      </div>
      <div className="document-details">
        <h3 title={document.filename}>{document.filename}</h3>
        <div className="document-meta">
          <span>{formatFileSize(document.size)}</span>
          <span className="document-meta-dot" aria-hidden="true" />
          <time dateTime={document.uploaded_at}>
            {new Date(document.uploaded_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })}
          </time>
        </div>
      </div>
      <button
        className="document-delete-button"
        type="button"
        onClick={() => onDelete(document.id)}
        disabled={isDeleting}
        aria-label={`Delete ${document.filename}`}
        title="Delete document"
      >
        {isDeleting ? (
          <span className="delete-spinner" aria-hidden="true" />
        ) : (
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M4.5 6h11M8 6V4.5h4V6m2.5 0-.6 9.5H6.1L5.5 6m2.8 2.5v4.5m3.4-4.5v4.5" />
          </svg>
        )}
      </button>
    </article>
  )
}
