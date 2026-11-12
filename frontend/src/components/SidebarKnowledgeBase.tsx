import type { DocumentSummary } from '../services/documentService'
import { DocumentList } from './DocumentList'
import { UploadPanel } from './UploadPanel'

interface SidebarKnowledgeBaseProps {
  documents: DocumentSummary[]
  isLoading: boolean
  isUploading: boolean
  uploadProgress: number
  uploadingFilename: string | null
  deletingId: string | null
  onUpload: (file: File) => Promise<boolean>
  onDelete: (documentId: string) => void
  onClose?: () => void
  mobile?: boolean
}

export function SidebarKnowledgeBase({
  documents,
  isLoading,
  isUploading,
  uploadProgress,
  uploadingFilename,
  deletingId,
  onUpload,
  onDelete,
  onClose,
  mobile = false,
}: SidebarKnowledgeBaseProps) {
  return (
    <aside className={`knowledge-sidebar ${mobile ? 'knowledge-sidebar--drawer' : ''}`}>
      <div className="sidebar-title-row">
        <div className="sidebar-title-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M5 4.5h9l5 5v10H5z" />
            <path d="M14 4.5v5h5M8.5 13h7M8.5 16.5h7" />
          </svg>
        </div>
        <div>
          <p className="sidebar-eyebrow">KNOWLEDGE BASE</p>
          <h2>Support library</h2>
        </div>
        {mobile && (
          <button
            className="drawer-close-button"
            type="button"
            onClick={onClose}
            aria-label="Close knowledge base"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="m5 5 10 10M15 5 5 15" />
            </svg>
          </button>
        )}
      </div>

      <UploadPanel
        isUploading={isUploading}
        uploadProgress={uploadProgress}
        uploadingFilename={uploadingFilename}
        onUpload={onUpload}
      />

      <div className="sidebar-divider" />

      <DocumentList
        documents={documents}
        isLoading={isLoading}
        deletingId={deletingId}
        onDelete={onDelete}
      />

      <div className="sidebar-footnote">
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <rect x="3.5" y="7" width="9" height="7" rx="1.5" />
          <path d="M5.5 7V5a2 2 0 0 1 4 0v2" />
        </svg>
        Your files stay in your workspace.
      </div>
    </aside>
  )
}
