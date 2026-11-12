import { useCallback, useEffect, useRef, useState } from 'react'
import {
  deleteDocument,
  getDocumentErrorMessage,
  getDocuments,
  uploadDocument,
} from '../services/documentService'
import type { DocumentSummary } from '../services/documentService'
import { DocumentCard } from './DocumentCard'

const ACCEPTED_TYPES = '.pdf,.docx,.txt'
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'txt'])

export function KnowledgeBase() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const refreshDocuments = useCallback(async () => {
    const result = await getDocuments()
    setLoadError(null)
    return result
  }, [])

  useEffect(() => {
    let isMounted = true

    void Promise.resolve()
      .then(getDocuments)
      .then((result) => {
        if (isMounted) {
          setDocuments(result)
          setLoadError(null)
        }
      })
      .catch((requestError: unknown) => {
        if (isMounted) setLoadError(getDocumentErrorMessage(requestError))
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  function handleFileChange(file: File | undefined) {
    setError(null)
    setLoadError(null)
    setNotice(null)
    if (!file) {
      setSelectedFile(null)
      return
    }

    const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ALLOWED_EXTENSIONS.has(extension)) {
      setSelectedFile(null)
      setError('Choose a PDF, DOCX, or TXT file.')
      if (inputRef.current) inputRef.current.value = ''
      return
    }

    setSelectedFile(file)
  }

  async function handleUpload() {
    if (!selectedFile || isUploading) return

    setError(null)
    setNotice(null)
    setUploadProgress(0)
    setIsUploading(true)

    try {
      await uploadDocument(selectedFile, setUploadProgress)
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
      setDocuments(await refreshDocuments())
      setNotice('Document uploaded successfully.')
    } catch (requestError: unknown) {
      setError(getDocumentErrorMessage(requestError))
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDelete(documentId: string) {
    if (deletingId) return

    setError(null)
    setNotice(null)
    setDeletingId(documentId)
    try {
      await deleteDocument(documentId)
      setDocuments((currentDocuments) =>
        currentDocuments.filter((document) => document.id !== documentId),
      )
      setNotice('Document deleted.')
    } catch (requestError: unknown) {
      setError(getDocumentErrorMessage(requestError))
    } finally {
      setDeletingId(null)
    }
  }

  function handleDrop(file: File | undefined) {
    setIsDragging(false)
    handleFileChange(file)
  }

  return (
    <main className="knowledge-page" aria-labelledby="knowledge-title">
      <section className="knowledge-intro">
        <div className="knowledge-heading">
          <div className="knowledge-heading-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M5 4.5h9l5 5v10H5z" />
              <path d="M14 4.5v5h5M8.5 13h7M8.5 16.5h7" />
            </svg>
          </div>
          <div>
            <p className="knowledge-eyebrow">KNOWLEDGE BASE</p>
            <h1 id="knowledge-title">Your support library</h1>
            <p className="knowledge-description">
              Add helpful guides and documents for your service desk assistant.
            </p>
          </div>
        </div>
      </section>

      <section className="upload-panel" aria-labelledby="upload-title">
        <div className="upload-panel-heading">
          <div>
            <h2 id="upload-title">Upload a document</h2>
            <p>Share a guide or reference with your AI assistant.</p>
          </div>
          <span className="supported-types">PDF · DOCX · TXT</span>
        </div>

        <div
          className={`upload-dropzone ${selectedFile ? 'upload-dropzone--selected' : ''} ${isUploading ? 'upload-dropzone--busy' : ''} ${isDragging ? 'upload-dropzone--dragging' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            if (!isUploading) setIsDragging(true)
          }}
          onDragLeave={(event) => {
            if (
              !(event.relatedTarget instanceof Node) ||
              !event.currentTarget.contains(event.relatedTarget)
            ) {
              setIsDragging(false)
            }
          }}
          onDrop={(event) => {
            event.preventDefault()
            handleDrop(event.dataTransfer.files[0])
          }}
        >
          <input
            ref={inputRef}
            className="sr-only"
            id="document-file"
            type="file"
            accept={ACCEPTED_TYPES}
            disabled={isUploading}
            onChange={(event) => handleFileChange(event.target.files?.[0])}
          />
          <div className="upload-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M12 15V4m0 0L8 8m4-4 4 4M5 14v5h14v-5" />
            </svg>
          </div>
          <div className="upload-copy">
            <p>
              {selectedFile ? (
                <strong>{selectedFile.name}</strong>
              ) : (
                <>
                  <label htmlFor="document-file">Choose a file</label>
                  <span> or drag it here</span>
                </>
              )}
            </p>
            <span>
              {selectedFile
                ? `${(selectedFile.size / 1024).toFixed(1)} KB · Ready to upload`
                : 'PDF, DOCX, or TXT'}
            </span>
          </div>
          <button
            className="upload-button"
            type="button"
            disabled={!selectedFile || isUploading}
            onClick={handleUpload}
          >
            {isUploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>

        {isUploading && (
          <div className="upload-progress" role="status" aria-live="polite">
            <div className="upload-progress-label">
              <span>Uploading {selectedFile?.name}</span>
              <span>{uploadProgress}%</span>
            </div>
            <div
              className="upload-progress-track"
              role="progressbar"
              aria-label="Upload progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={uploadProgress}
            >
              <span style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}

        <p className="upload-guidance">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="8" cy="8" r="6" />
            <path d="M8 7v3.5M8 5h.01" />
          </svg>
          Documents are stored securely and can be removed at any time.
        </p>
      </section>

      <section className="documents-section" aria-labelledby="documents-title">
        <div className="documents-heading">
          <div>
            <h2 id="documents-title">Uploaded documents</h2>
            <p>Your reference files in one place.</p>
          </div>
          <span className="document-count">
            {documents.length} {documents.length === 1 ? 'document' : 'documents'}
          </span>
        </div>

        {(loadError || error) && (
          <div className="knowledge-alert knowledge-alert--error" role="alert">
            <span>{loadError ?? error}</span>
            {loadError ? (
              <button
                type="button"
                onClick={() => {
                  setIsLoading(true)
                  refreshDocuments()
                    .then(setDocuments)
                    .catch((requestError: unknown) =>
                      setLoadError(getDocumentErrorMessage(requestError)),
                    )
                    .finally(() => setIsLoading(false))
                }}
              >
                Try again
              </button>
            ) : (
              <button type="button" onClick={() => setError(null)}>
                Dismiss
              </button>
            )}
          </div>
        )}
        {notice && (
          <div className="knowledge-alert knowledge-alert--success" role="status">
            {notice}
          </div>
        )}

        {isLoading ? (
          <div className="documents-loading" role="status">
            <span className="loading-spinner" />
            Loading documents…
          </div>
        ) : loadError ? null : documents.length > 0 ? (
          <div className="document-list">
            {documents.map((document) => (
              <DocumentCard
                key={document.id}
                document={document}
                isDeleting={deletingId === document.id}
                onDelete={handleDelete}
              />
            ))}
          </div>
        ) : (
          <div className="documents-empty">
            <div className="empty-folder-icon" aria-hidden="true">
              <svg viewBox="0 0 40 40">
                <path d="M6 12.5h11l3 3h14v15H6z" />
                <path d="M6 16h28" />
                <path d="m16 24 4 4 6-7" />
              </svg>
            </div>
            <h3>No documents yet</h3>
            <p>Upload a PDF, DOCX, or TXT file to get started.</p>
          </div>
        )}
      </section>
    </main>
  )
}
